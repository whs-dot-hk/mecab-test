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

            # Debug the specific pattern for words like "男の子"
            kanji_positions = [i for i, char in enumerate(surface) if is_kanji(char)]
            kana_positions = [
                i
                for i, char in enumerate(surface)
                if not is_kanji(char) and "\u3040" <= char <= "\u30ff"
            ]

            # Special handling for kanji separated by kana
            if (
                len(kanji_positions) > 1
                and len(kana_positions) > 0
                and kana_positions[0] > kanji_positions[0]
            ):
                # We have kanji-kana-kanji pattern like "男の子"
                processed_surface = ""

                # Track positions
                current_pos = 0
                reading_pos = 0

                # Process each character
                i = 0
                while i < len(surface):
                    if is_kanji(surface[i]):
                        # Find group of consecutive kanji
                        kanji_start = i
                        while i < len(surface) and is_kanji(surface[i]):
                            i += 1
                        kanji_end = i

                        # Extract this kanji group
                        kanji_group = surface[kanji_start:kanji_end]

                        # Find reading for this kanji group
                        # Look for the next kana character in surface
                        next_kana_pos = -1
                        for j in range(kanji_end, len(surface)):
                            if "\u3040" <= surface[j] <= "\u30ff":
                                next_kana_pos = j
                                break

                        # If there's a next kana, find where it appears in the reading
                        if next_kana_pos != -1:
                            next_kana = surface[next_kana_pos]
                            next_kana_reading_pos = reading.find(next_kana, reading_pos)

                            if next_kana_reading_pos != -1:
                                # Found the kana in the reading
                                kanji_reading = reading[
                                    reading_pos:next_kana_reading_pos
                                ]
                                reading_pos = next_kana_reading_pos
                            else:
                                # Couldn't find the kana, use proportional approach
                                chars_left = sum(
                                    1
                                    for j in range(kanji_start, len(surface))
                                    if is_kanji(surface[j])
                                )
                                reading_left = len(reading) - reading_pos
                                this_reading_len = reading_left // max(1, chars_left)
                                kanji_reading = reading[
                                    reading_pos : reading_pos + this_reading_len
                                ]
                                reading_pos += this_reading_len
                        else:
                            # This is the last kanji group, use the rest of the reading
                            kanji_reading = reading[reading_pos:]
                            reading_pos = len(reading)

                        # Add ruby tag for this kanji group
                        processed_surface += f"<ruby><rb>{kanji_group}</rb><rt>{kanji_reading}</rt></ruby>"
                    else:
                        # Add non-kanji character as-is
                        processed_surface += surface[i]

                        # If it's a kana character, move the reading position forward
                        if "\u3040" <= surface[i] <= "\u30ff":
                            if (
                                reading_pos < len(reading)
                                and surface[i] == reading[reading_pos]
                            ):
                                reading_pos += 1

                        i += 1

                result.append(processed_surface)
                continue

            # Pattern matching for specific word types
            if len(surface) == len(reading) and all(
                surface[i] == reading[i] if not is_kanji(surface[i]) else True
                for i in range(len(surface))
            ):
                # Perfect match between surface and reading for non-kanji chars
                # Examples: "男の子" (otoko no ko), "私は" (watashi wa)

                processed_surface = ""
                i = 0
                while i < len(surface):
                    if is_kanji(surface[i]):
                        # Find consecutive kanji
                        start = i
                        while i < len(surface) and is_kanji(surface[i]):
                            i += 1
                        end = i

                        # Extract reading for this kanji group
                        # First, find where this kanji group's reading ends in the full reading
                        reading_end = end
                        while reading_end < len(reading) and (
                            end >= len(surface) or surface[end] != reading[reading_end]
                        ):
                            reading_end += 1

                        kanji_reading = reading[start:reading_end]
                        kanji_surface = surface[start:end]

                        processed_surface += f"<ruby><rb>{kanji_surface}</rb><rt>{kanji_reading}</rt></ruby>"
                    else:
                        # Non-kanji character, add as-is
                        processed_surface += surface[i]
                        i += 1

                result.append(processed_surface)
                continue

            # For verbs and adjectives where only the first part is kanji

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
