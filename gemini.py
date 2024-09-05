import google.generativeai as genai
import os

genai.configure(api_key="AIzaSyDumg9TywXB-wdrcVqkCkuVF1_Ml2X2FWw")
#genai.configure(api_key=os.environ["API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content("Who is Stapleton Meats")
print(response.text)