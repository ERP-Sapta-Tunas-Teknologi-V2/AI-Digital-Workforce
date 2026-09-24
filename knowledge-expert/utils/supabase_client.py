import httpx
from supabase import create_client, ClientOptions
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=ClientOptions(
        httpx_client=httpx.Client(http2=False, timeout=30)
    )
)