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

            # Use MeCab to get readings for individual kanji characters
            processed_surface = ""

            # Create character to reading mapping
            if len(surface) == len(reading):
                # Simple 1:1 mapping
                for i, char in enumerate(surface):
                    if is_kanji(char):
                        processed_surface += (
                            f"<ruby><rb>{char}</rb><rt>{reading[i]}</rt></ruby>"
                        )
                    else:
                        processed_surface += char
            else:
                # For more complex words with kanji that map to multiple kana
                # Get the kana-only version of the surface form
                kana_only = ""
                for char in surface:
                    if is_kanji(char):
                        continue
                    if "\u3040" <= char <= "\u30ff":  # Hiragana/katakana range
                        kana_only += char

                # Initialize the reading position
                reading_pos = 0

                # Process each character
                for char in surface:
                    if not is_kanji(char):
                        processed_surface += char
                        # If it's kana, advance reading position to skip this character
                        if "\u3040" <= char <= "\u30ff":
                            reading_pos += 1
                    else:
                        # This is kanji, find its reading
                        # Find where in the reading this kanji's reading ends
                        # by matching the next kana in surface with reading

                        # Find next kana in surface after this kanji
                        next_kana_pos = -1
                        for i in range(surface.index(char) + 1, len(surface)):
                            if "\u3040" <= surface[i] <= "\u30ff":
                                next_kana_pos = i
                                break

                        # If there's no next kana, the reading goes to the end
                        if next_kana_pos == -1:
                            char_reading = reading[reading_pos:]
                            reading_pos = len(reading)
                        else:
                            # Otherwise, find where in reading the next kana appears
                            next_kana = surface[next_kana_pos]
                            next_kana_reading_pos = reading.find(next_kana, reading_pos)

                            if next_kana_reading_pos == -1:
                                # Fallback if we can't find the next kana in reading
                                char_reading = reading[reading_pos:]
                                reading_pos = len(reading)
                            else:
                                char_reading = reading[
                                    reading_pos:next_kana_reading_pos
                                ]
                                reading_pos = next_kana_reading_pos

                        processed_surface += (
                            f"<ruby><rb>{char}</rb><rt>{char_reading}</rt></ruby>"
                        )

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
