import re
import sys
import MeCab
from bs4 import BeautifulSoup, NavigableString

def is_kanji(char):
    """Check if a character is a kanji"""
    return '\u4E00' <= char <= '\u9FFF'

def add_furigana(text, mecab_tagger):
    """Add furigana to Japanese text using MeCab"""
    if not text.strip():
        return text
    
    # Check if text contains kanji
    if not any(is_kanji(char) for char in text):
        return text
    
    result = []
    parsed = mecab_tagger.parse(text).split('\n')
    
    for line in parsed:
        if line == 'EOS' or not line:
            continue
            
        parts = line.split('\t')
        if len(parts) < 2:
            continue
            
        surface = parts[0]
        features = parts[1].split(',')
        
        # Only add furigana to kanji
        if any(is_kanji(char) for char in surface) and len(features) > 7 and features[7] != '*':
            reading = features[7]
            # Convert katakana reading to hiragana for furigana
            reading = ''.join(chr(ord(char) - 96) if '\u30A1' <= char <= '\u30F6' else char for char in reading)
            # Create ruby markup
            ruby = f'<ruby><rb>{surface}</rb><rt>{reading}</rt></ruby>'
            result.append(ruby)
        else:
            result.append(surface)
    
    return ''.join(result)

def process_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    mecab_tagger = MeCab.Tagger("-d /usr/lib/x86_64-linux-gnu/mecab/dic/mecab-ipadic-neologd")
    
    def process_node(node):
        # Skip existing ruby tags to preserve them
        if node.name == 'ruby':
            return
        
        # Process text nodes
        if isinstance(node, NavigableString):
            if node.parent.name not in ['rt', 'rb']:
                new_content = add_furigana(str(node), mecab_tagger)
                if new_content != str(node):
                    new_soup = BeautifulSoup(new_content, 'html.parser')
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
        with open(input_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        processed_html = process_html(html_content)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(processed_html)
            
        print(f"Processed HTML saved to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
