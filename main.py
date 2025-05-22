import re
import sys
import MeCab
from bs4 import BeautifulSoup, NavigableString


def is_kanji(char):
    """Check if a character is a kanji"""
    return "\u4e00" <= char <= "\u9fff"


def add_furigana(text, mecab_tagger):
    """Add furigana to Japanese text using MeCab"""
    if not text.strip():
        return text

    # Check if text contains kanji
    if not any(is_kanji(char) for char in text):
        return text

    result = []
    parsed = mecab_tagger.parse(text).split("\n")

    for line in parsed:
        if line == "EOS" or not line:
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            continue

        surface = parts[0]
        features = parts[1].split(",")

        # Only add furigana if we have reading information and contains kanji
        if (
            any(is_kanji(char) for char in surface)
            and len(features) > 7
            and features[7] != "*"
        ):
            reading = features[7]
            # Convert katakana reading to hiragana for furigana
            reading = "".join(
                chr(ord(char) - 96) if "\u30a1" <= char <= "\u30f6" else char
                for char in reading
            )

            # For verbs and adjectives where only the first part is kanji
            kanji_positions = [i for i, char in enumerate(surface) if is_kanji(char)]

            # Use a single ruby tag for consecutive kanji
            consecutive_kanji_groups = []
            current_group = []

            for i, char in enumerate(surface):
                if is_kanji(char):
                    current_group.append(i)
                elif current_group:
                    consecutive_kanji_groups.append(current_group)
                    current_group = []

            # Don't forget the last group if it exists
            if current_group:
                consecutive_kanji_groups.append(current_group)

            # Special handling for words with kanji followed by hiragana ending
            if kanji_positions and kanji_positions[-1] < len(surface) - 1:
                # Verb/adjective pattern with hiragana ending

                # Find the last kanji position
                last_kanji_pos = kanji_positions[-1]

                # The kanji part (beginning of the word)
                kanji_part = surface[: last_kanji_pos + 1]

                # The kana part (ending of the word)
                kana_part = surface[last_kanji_pos + 1 :]

                # Simple approach: look for the kana ending in the reading
                found = False
                for i in range(len(reading) - len(kana_part) + 1):
                    if reading[i : i + len(kana_part)] == kana_part:
                        # Found the kana ending in the reading
                        kanji_reading = reading[:i]
                        found = True
                        break

                if not found:
                    # Fallback: distribute readings for kanji only
                    kanji_reading = reading[: len(reading) - len(kana_part)]

                # Process the word with a single ruby tag for all consecutive kanji
                processed_surface = ""

                # Check if all kanji are consecutive at the beginning
                if all(pos == i for i, pos in enumerate(kanji_positions)):
                    # All kanji are consecutive at the beginning, use a single ruby tag
                    processed_surface = f"<ruby><rb>{kanji_part}</rb><rt>{kanji_reading}</rt></ruby>{kana_part}"
                else:
                    # Handle non-consecutive kanji in verbs (rare but possible)
                    current_pos = 0
                    for group in consecutive_kanji_groups:
                        if not group:
                            continue

                        # Extract this kanji group
                        start_pos = group[0]
                        end_pos = group[-1] + 1

                        # Add any kana between last position and start of this group
                        if start_pos > current_pos:
                            processed_surface += surface[current_pos:start_pos]

                        # Calculate reading for this kanji group
                        group_len = end_pos - start_pos
                        group_reading_len = int(
                            len(kanji_reading) * (group_len / len(kanji_part))
                        )
                        group_reading = kanji_reading[
                            len(processed_surface)
                            - len(kana_part) : len(processed_surface)
                            - len(kana_part)
                            + group_reading_len
                        ]

                        # Add ruby for this group
                        processed_surface += f"<ruby><rb>{surface[start_pos:end_pos]}</rb><rt>{group_reading}</rt></ruby>"
                        current_pos = end_pos

                    # Add remaining kana
                    if current_pos < len(surface):
                        processed_surface += surface[current_pos:]

            else:
                # Regular case (words without clear verb/adjective pattern)
                # For multi-kanji compounds, use a single ruby tag for consecutive kanji
                processed_surface = ""
                current_pos = 0

                # If the word is all kanji or all consecutive kanji, use a single ruby tag
                if len(kanji_positions) > 1 and all(
                    kanji_positions[i] == kanji_positions[0] + i
                    for i in range(len(kanji_positions))
                ):
                    # All kanji are consecutive
                    kanji_part = "".join(surface[pos] for pos in kanji_positions)
                    processed_surface = (
                        f"<ruby><rb>{kanji_part}</rb><rt>{reading}</rt></ruby>"
                    )

                    # Add any remaining non-kanji
                    for i, char in enumerate(surface):
                        if i not in kanji_positions:
                            processed_surface += char
                else:
                    # Process each consecutive kanji group
                    for group in consecutive_kanji_groups:
                        if not group:
                            continue

                        # Add any non-kanji characters before this group
                        if group[0] > current_pos:
                            processed_surface += surface[current_pos : group[0]]

                        # For a group of consecutive kanji, use a single ruby tag
                        if len(group) > 1:
                            # Extract this kanji group
                            group_text = surface[group[0] : group[-1] + 1]

                            # Calculate reading for this group (proportional to its length)
                            total_kanji = sum(1 for c in surface if is_kanji(c))
                            group_reading_len = int(
                                len(reading) * (len(group) / total_kanji)
                            )

                            # Distribute reading across groups proportionally
                            start_idx = int(
                                len(reading)
                                * (
                                    sum(
                                        1
                                        for i in range(group[0])
                                        if is_kanji(surface[i])
                                    )
                                    / total_kanji
                                )
                            )
                            group_reading = reading[
                                start_idx : start_idx + group_reading_len
                            ]

                            processed_surface += f"<ruby><rb>{group_text}</rb><rt>{group_reading}</rt></ruby>"
                        else:
                            # Single kanji
                            char_idx = group[0]
                            char = surface[char_idx]

                            # Calculate reading for this single kanji
                            total_kanji = sum(1 for c in surface if is_kanji(c))
                            kanji_index = sum(
                                1 for i in range(char_idx) if is_kanji(surface[i])
                            )

                            # Proportional reading distribution
                            reading_start = int(
                                len(reading) * (kanji_index / total_kanji)
                            )
                            reading_end = int(
                                len(reading) * ((kanji_index + 1) / total_kanji)
                            )

                            char_reading = reading[reading_start:reading_end]
                            processed_surface += (
                                f"<ruby><rb>{char}</rb><rt>{char_reading}</rt></ruby>"
                            )

                        current_pos = group[-1] + 1

                    # Add any remaining characters
                    if current_pos < len(surface):
                        processed_surface += surface[current_pos:]

            result.append(processed_surface)
        else:
            result.append(surface)

    return "".join(result)


def process_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    mecab_tagger = MeCab.Tagger(
        "-r/dev/null -d /usr/lib/x86_64-linux-gnu/mecab/dic/mecab-ipadic-neologd"
    )

    def process_node(node):
        # Skip existing ruby tags to preserve them
        if node.name == "ruby":
            return

        # Process text nodes
        if isinstance(node, NavigableString):
            if node.parent.name not in ["rt", "rb"]:
                new_content = add_furigana(str(node), mecab_tagger)
                if new_content != str(node):
                    new_soup = BeautifulSoup(new_content, "html.parser")
                    node.replace_with(*new_soup.contents)
        else:
            # Process child nodes
            for child in list(node.children):
                process_node(child)

    # Start processing from the root
    for node in soup.contents:
        process_node(node)

    return str(soup)


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <input_html_file> [output_html_file]")
        return

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file + ".processed.html"

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            html_content = f.read()

        processed_html = process_html(html_content)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(processed_html)

        print(f"Processed HTML saved to {output_file}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
