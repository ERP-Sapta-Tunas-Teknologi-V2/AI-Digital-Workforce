import base64
from functools import lru_cache
from langchain_core.messages import HumanMessage

from config import VISION_MODEL
from utils.ollama_client import get_llm

@lru_cache(maxsize=1)
def _vision_llm():
    if not VISION_MODEL:
        raise RuntimeError("VISION_MODEL belum diset")
    return get_llm(model=VISION_MODEL, keep_alive=0)

def describe_image(image_bytes: str) -> str:
    """Generate a detailed text description of an image using a local Ollama vision model via LangChain."""

    image_data = base64.b64encode(image_bytes).decode("utf-8")

    message = HumanMessage(content=[
        {
            "type": "text",
            "text": (
                "Deskripsikan gambar ini dalam Bahasa Indonesia untuk retrieval. "
                "Di baris pertama, tulis header nama gambar dengan '## ' di awal"
                "Sebutkan semua teks, label, komponen, dan koneksi yang terlihat. "
                "Jangan terjemahkan tulisan yang berbahasa Inggris atau bahasa asing lainnya apa adanya. "
                "Jelaskan alur jika ada sesuai panah dan koneksi. "
                "Jangan menerjemahkan atau mengarang informasi. "
                "Jika tidak terbaca, nyatakan tidak terbaca."
            ),
        },
        {
            "type": "image_url",
            "image_url": f"data:image/png;base64,{image_data}",
        },
    ])

    response = _vision_llm().invoke([message])
    return response.content