import base64
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

from config import VISION_MODEL

vision_llm = ChatOllama(model=VISION_MODEL, temperature=0, num_ctx=8192, reasoning=False)

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

    response = vision_llm.invoke([message])
    return response.content