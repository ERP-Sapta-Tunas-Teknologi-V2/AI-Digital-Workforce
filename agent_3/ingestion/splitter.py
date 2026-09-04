from langchain_core.documents import Document
from transformers import AutoTokenizer
import hashlib
import re

from utils.injection_patterns import INJECTION_PATTERNS
from config.settings import LOCAL_EMB_MODEL

class StructureAwareChunker:
    def __init__(self, max_tokens=1000):
        self.tokenizer = AutoTokenizer.from_pretrained(f"BAAI/{LOCAL_EMB_MODEL}")
        self.max_tokens = max_tokens

    def _scan_injection(self, content):
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                content = re.sub(pattern, "[REDACTED]", content, flags=re.IGNORECASE)
        return content

    def _extract_item_text(self, item, doc):
        text = getattr(item, "text", None) or getattr(item, "orig", None)
        if text and text.strip():
            return text

        if hasattr(item, "export_to_markdown"):
            try:
                text = item.export_to_markdown(doc=doc)
                if text and text.strip():
                    return text
            except Exception:
                pass

        return None

    def _create_chunks(self, blocks, source, document_id, uploaded_at):
        sections = self._build_sections(blocks)
        documents = []
        chunk_index = 0

        for section in sections:
            for chunk in self._chunk_section(section):
                documents.append(Document(
                    page_content=chunk["content"],
                    metadata={
                        "source": source,
                        "document_id": document_id,
                        "chunk_index": chunk_index,
                        "page": chunk["pages"],
                        "section_title": section["title"],
                        "uploaded_at": uploaded_at,
                        "fingerprint": chunk["fingerprint"]
                    }
                ))
                chunk_index += 1

        return documents

    def split_document(self, page_documents, source, document_id, uploaded_at):
        blocks = []

        for page_document in page_documents:
            page_number = page_document["page"]
            docling_doc = page_document["document"]

            for item, level in docling_doc.iterate_items():
                label = getattr(getattr(item, "label", None), "value", None)
                if label == "picture": 
                    continue

                text = self._extract_item_text(item, docling_doc)
                if not text or not text.strip(): 
                    continue

                blocks.append({
                    "text": text.strip(), 
                    "label": label, 
                    "level": level, 
                    "pages": [page_number]
                })

        return self._create_chunks(blocks, source, document_id, uploaded_at)

    def _build_sections(self, blocks):
        sections = []
        current_section = None
        previous_was_header = False

        for block in blocks:
            is_header = block["label"] == "section_header"

            if is_header and not previous_was_header:
                if current_section:
                    sections.append(current_section)

                current_section = {
                    "title": block["text"],
                    "section": self._extract_section_number(block["text"]),
                    "blocks": []
                }

            elif current_section:
                current_section["blocks"].append(block)
                
            else:
                current_section = {
                    "title": None,
                    "section": None,
                    "blocks": [block]
                }

            previous_was_header = is_header

        if current_section:
            sections.append(current_section)

        return sections

    def _chunk_section(self, section):
        chunks = []
        current_blocks = []
        current_tokens = 0
        heading = section["title"]

        heading_tokens = len(
            self.tokenizer.encode(heading, add_special_tokens=False)
        ) if heading else 0

        max_content_tokens = self.max_tokens - heading_tokens

        for block in section["blocks"]:
            text = block["text"]
            tokens = len(self.tokenizer.encode(text, add_special_tokens=False))

            if block["label"] == "table" and tokens > max_content_tokens:
                if current_blocks:
                    chunks.append(self._make_chunk(current_blocks, heading))
                    current_blocks = []
                    current_tokens = 0

                for part in self._split_table_block(block, max_content_tokens):
                    chunks.append(self._make_chunk([part], heading))

                continue

            if tokens > max_content_tokens:
                if current_blocks:
                    chunks.append(self._make_chunk(current_blocks, heading))
                    current_blocks = []
                    current_tokens = 0

                for part in self._split_text_block(block, max_content_tokens):
                    chunks.append(self._make_chunk([part], heading))

                continue

            if current_blocks and current_tokens + tokens > max_content_tokens:
                chunks.append(self._make_chunk(current_blocks, heading))
                current_blocks = []
                current_tokens = 0

            current_blocks.append(block)
            current_tokens += tokens

        if current_blocks:
            chunks.append(self._make_chunk(current_blocks, heading))

        return chunks

    def _split_table_block(self, block, max_tokens):
        lines = block["text"].splitlines()

        if len(lines) <= 2:
            return [block]

        header = lines[:2]
        data_rows = lines[2:]

        parts = []
        current_lines = header.copy()
        current_tokens = len(
            self.tokenizer.encode("\n".join(current_lines), add_special_tokens=False)
        )

        for row in data_rows:
            row_tokens = len(
                self.tokenizer.encode(row, add_special_tokens=False)
            )

            if current_lines != header and current_tokens + row_tokens > max_tokens:
                parts.append({**block, "text": "\n".join(current_lines)})
                current_lines = header.copy()
                current_tokens = len(
                    self.tokenizer.encode("\n".join(current_lines), add_special_tokens=False)
                )

            current_lines.append(row)
            current_tokens += row_tokens

        if len(current_lines) > len(header):
            parts.append({**block, "text": "\n".join(current_lines)})

        return parts

    def _split_text_block(self, block, max_tokens):
        tokens = self.tokenizer.encode(
            block["text"],
            add_special_tokens=False
        )

        return [
            {
                **block,
                "text": self.tokenizer.decode(
                    tokens[i:i + max_tokens],
                    skip_special_tokens=True
                )
            }
            for i in range(0, len(tokens), max_tokens)
        ]

    def _make_chunk(self, blocks, heading):
        content = "\n\n".join(block["text"] for block in blocks)
        content = self._scan_injection(content)
        content = f"{content}\n\nSapta Tunas Teknologi (STT)"

        if heading:
            content = f"{heading}\n\n{content}"

        tokens = len(self.tokenizer.encode(content, add_special_tokens=False))

        if tokens > self.max_tokens:
            print(
                f"WARNING: chunk exceeds limit: "
                f"{tokens} tokens | heading={heading!r}"
            )

        pages = []
        for block in blocks:
            for page in block["pages"]:
                if page not in pages:
                    pages.append(page)

        return {
            "content": content,
            "pages": pages,
            "fingerprint": hashlib.sha256(content.encode("utf-8")).hexdigest()
        }

    def _extract_section_number(self, title):
        if not title:
            return None

        parts = title.split()

        if parts and parts[0] and parts[0][0].isdigit():
            return parts[0]

        return None