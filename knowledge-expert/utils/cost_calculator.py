EMB_PRICING_PER_MILLION_TOKENS = {
    "bge-m3": {"embedding": 0},
    "voyage-4-large": {"embedding": 0.12},
    "voyage-4-lite": {"embedding": 0.02},
}

LLM_PRICING_PER_MILLION_TOKENS = {
    "qwen2.5:14b": {"input": 0, "output": 0},
}

def calculate_emb_cost(emb_model, embedding_tokens):
    price = EMB_PRICING_PER_MILLION_TOKENS.get(emb_model)
    if not price: raise ValueError(f"Unknown embedding model: {emb_model}")
    price_per_token = price["embedding"] / 1_000_000

    emb_cost = embedding_tokens * price_per_token
    return emb_cost

def calculate_llm_cost(llm_model, input_tokens, output_tokens):
    price = LLM_PRICING_PER_MILLION_TOKENS.get(llm_model)
    if not price: raise ValueError(f"Unknown embedding model: {llm_model}")
    input_price_per_token = price["input"] / 1_000_000
    output_price_per_token = price["output"] / 1_000_000

    input_cost = input_tokens * input_price_per_token
    output_cost = output_tokens * output_price_per_token
    llm_cost = input_cost + output_cost

    return input_cost, output_cost, llm_cost

def calculate_cost(emb_model, llm_model, embedding_tokens, input_tokens, output_tokens):
    emb_cost = calculate_emb_cost(emb_model, embedding_tokens)
    input_cost, output_cost, llm_cost = calculate_llm_cost(llm_model, input_tokens, output_tokens)
    return emb_cost, llm_cost, input_cost, output_cost