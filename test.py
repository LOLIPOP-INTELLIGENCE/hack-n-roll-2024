api_key = 'AIzaSyA9rnUXpz3roR-Pk7PCZezo8j558I7dJv8'

import pathlib
import textwrap

import google.generativeai as genai

from IPython.display import display
from IPython.display import Markdown


def to_markdown(text):
  text = text.replace('•', '  *')
  return Markdown(textwrap.indent(text, '> ', predicate=lambda _: True))

genai.configure(api_key=api_key)

import PIL.Image

img = PIL.Image.open('label.png')

model = genai.GenerativeModel('gemini-pro-vision')

response = model.generate_content(["Can you describe this image in detail?", img], stream=True)

for chunk in response:
  print(chunk.text)
  print("_"*80)



