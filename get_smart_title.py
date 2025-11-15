def get_smart_title(
    node_content: str, max_words_per_line: int = 8, max_lines: int = 2
) -> str:
    """
    Intelligently truncate node content for graphviz display.

    Args:
        node_content: The full text content for the node
        max_words_per_line: Maximum words per line (default: 10)
        max_lines: Maximum number of lines (default: 2)

    Returns:
        A formatted string with up to max_lines, each with ~max_words_per_line words
    """
    # Clean and normalize the text
    text = " ".join(node_content.strip().split())

    # Split into words
    words = text.split()

    # If content fits in one line, return as is
    if len(words) <= max_words_per_line:
        return text

    lines = []
    current_line_words = []
    word_idx = 0

    for line_num in range(max_lines):
        if word_idx >= len(words):
            break

        # Collect words for this line
        target_words = max_words_per_line
        while word_idx < len(words) and len(current_line_words) < target_words:
            current_line_words.append(words[word_idx])
            word_idx += 1

        # If this is not the last line and there are more words, find a good break point
        if line_num < max_lines - 1 and word_idx < len(words):
            current_line_words = find_natural_break(current_line_words, words, word_idx)
            word_idx = word_idx - (target_words - len(current_line_words))

        lines.append(" ".join(current_line_words))
        current_line_words = []

    # Add ellipsis if there's more content
    if word_idx < len(words):
        lines[-1] = lines[-1] + "..."

    return "\n".join(lines)


def find_natural_break(current_words: list, all_words: list, next_idx: int) -> list:
    """
    Find a natural breaking point by looking for punctuation or complete phrases.
    """
    if not current_words:
        return current_words

    # Look for punctuation marks that indicate natural breaks
    break_punctuation = {",", ";", ":", ".", "!", "?"}

    # Check last few words for punctuation
    for i in range(len(current_words) - 1, max(0, len(current_words) - 4), -1):
        word = current_words[i]
        # If word ends with break punctuation, break after it
        if any(word.endswith(p) for p in break_punctuation):
            return current_words[: i + 1]

    # Check if breaking here would split a common phrase pattern
    # Look at next word to avoid breaking "the dog", "of the", etc.
    if next_idx < len(all_words):
        last_word = current_words[-1].lower().rstrip(".,;:!?")
        next_word = all_words[next_idx].lower()

        # Articles, prepositions, conjunctions - don't break before these
        dont_break_before = {
            "the",
            "a",
            "an",
            "of",
            "in",
            "on",
            "at",
            "to",
            "for",
            "and",
            "or",
            "but",
            "with",
            "from",
            "by",
        }

        # If next word is in the list, remove last word to avoid breaking
        if next_word in dont_break_before and len(current_words) > 3:
            return current_words[:-1]

    return current_words


# Example usage and tests
if __name__ == "__main__":
    test_cases = [
        "Short text",
        "This is a medium length text that should fit on one line comfortably",
        "This is a longer piece of text that will need to be broken into multiple lines for display in a graphviz node because it contains too many words",
        "The quick brown fox jumps over the lazy dog. Meanwhile, in the forest, other animals were preparing for winter.",
        "Natural Language Processing, Machine Learning, and Deep Learning are important fields in Computer Science",
        "A very long technical description: The transformer architecture uses self-attention mechanisms to process sequential data in parallel, which enables efficient training on large datasets and has revolutionized natural language processing tasks.",
    ]

    print("Testing get_smart_title() function:\n")
    for i, text in enumerate(test_cases, 1):
        print(f"Test {i}:")
        print(f"Original: {text}")
        print(f"Title:\n{get_smart_title(text)}")
        print("-" * 60)
