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

            # Count the number of kanji in the surface form
            kanji_count = sum(1 for char in surface if is_kanji(char))
            if kanji_count == 0:
                result.append(surface)
                continue

            # Process kanji sequences with proper reading distribution
            # First, identify kanji positions and non-kanji (kana) positions
            char_types = []  # 1 for kanji, 0 for non-kanji
            for char in surface:
                char_types.append(1 if is_kanji(char) else 0)

            # Remove kana characters from reading that correspond to kana in surface
            reading_for_kanji = reading
            reading_pos = 0
            for i, char in enumerate(surface):
                if not is_kanji(char) and "\u3040" <= char <= "\u30ff":
                    # This is a kana character, remove corresponding kana from reading
                    if reading_pos < len(reading_for_kanji):
                        reading_for_kanji = (
                            reading_for_kanji[:reading_pos]
                            + reading_for_kanji[reading_pos + 1 :]
                        )
                    else:
                        # We've reached the end of the reading
                        break
                else:
                    reading_pos += 1

            # Now distribute the remaining reading (reading_for_kanji) among kanji characters
            # For simplicity, try to distribute evenly
            reading_per_kanji = len(reading_for_kanji) // kanji_count
            remainder = len(reading_for_kanji) % kanji_count

            # Generate the processed text with ruby tags
            processed_surface = ""
            kanji_index = 0
            reading_start = 0

            for i, char in enumerate(surface):
                if is_kanji(char):
                    # Calculate how many kana this kanji gets
                    char_reading_len = reading_per_kanji
                    if kanji_index < remainder:
                        char_reading_len += 1

                    # Extract this kanji's reading
                    if reading_start + char_reading_len <= len(reading_for_kanji):
                        char_reading = reading_for_kanji[
                            reading_start : reading_start + char_reading_len
                        ]
                    else:
                        char_reading = reading_for_kanji[reading_start:]

                    # Add ruby tag
                    processed_surface += (
                        f"<ruby><rb>{char}</rb><rt>{char_reading}</rt></ruby>"
                    )

                    # Update counters
                    reading_start += char_reading_len
                    kanji_index += 1
                else:
                    # For non-kanji characters, just add them as is
                    processed_surface += char

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
