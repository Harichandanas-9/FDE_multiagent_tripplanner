"""Web search stub."""
GENERIC_TIPS = ["Carry photocopies of ID","Note local emergency numbers",
                 "Inform your bank of travel dates"]


def web_search(query: str):
    return {"query": query, "tips": GENERIC_TIPS}
