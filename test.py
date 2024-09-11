import re

# Example text with various Australian numbers
text = "Here are some numbers: 0458 674 848, +61 2 4088 7485, +61 (0)421 355 500, 434724056"

# Regular expression for Australian phone numbers
australian_phone_regex = re.compile(r'''
    (
        (\+61\s?\(0\)|\+61\s?|0)?   # Optional +61 with or without (0) or a leading 0
        [\s\-\.]?                   # Optional separator (space, dash, dot)
        (\d{1,2})?                  # Optional area code (1-2 digits) for landlines
        [\s\-\.]?                   # Optional separator
        \d{1,4}                     # First block (1 to 4 digits, depending on format)
        [\s\-\.]?                   # Optional separator
        \d{3,4}                     # Second block (3 to 4 digits)
        [\s\-\.]?                   # Optional separator
        \d{3,4}                     # Third block (3 to 4 digits)
    )
''', re.VERBOSE)

# Find all matches
matches = australian_phone_regex.findall(text)

# Print out the matched phone numbers
for match in matches:
    print(match[0])
