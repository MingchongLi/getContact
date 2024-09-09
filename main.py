from openai import OpenAI
import os
import requests
import google.generativeai as genai
from bs4 import BeautifulSoup
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import json
import re
from selenium.webdriver.common.by import By


def init_web_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service(ChromeDriverManager().install())
    browser_driver = webdriver.Chrome(service=service, options=options)

    return browser_driver


def ask_gpt(text):
    client = OpenAI(
        api_key=os.environ.get("GPT"),
    )
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": text
            }
        ],
        model="gpt-4o",
        max_tokens=500
    )
    print(f"token used: {chat_completion.usage.total_tokens}")
    return chat_completion.choices[0].message.content


# Function to extract phone numbers and emails
def find_contacts(browser_driver, site):
    # Get the page source
    page_source = browser_driver.execute_script("""
            return document.body.innerText;
        """).lower()

    # Regex pattern for emails
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, page_source)

    # Regex pattern for phone numbers with +61 or nearby "phone", "mobile", etc.
    phone_pattern = r'(\+61\s?\d{1,3}[\s-]?\d{1,4}[\s-]?\d{1,4})|\b(?:phone|mobile|telephone)\b.*?(\d{9,})'
    phones = re.findall(phone_pattern, page_source, re.IGNORECASE)

    # Extract 'tel' href links
    tel_links = browser_driver.find_elements(By.CSS_SELECTOR, 'a[href^="tel:"]')
    tel_numbers = [link.get_attribute('href').replace('tel:', '') for link in tel_links]

    # Combine all phone numbers found
    all_phones = list(set([phone for phone_group in phones for phone in phone_group if phone] + tel_numbers))

    return {
        'site': site,
        'emails': list(set(emails)),
        'phones': all_phones
    }


def ask_gemini(text):
    genai.configure(api_key=os.environ["GEMINI"])
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(text)
    try:
        return response.text
    except Exception as e:
        print(e)
        return ""


def clean_url(src):
    cleaned_url = src.strip().encode('ascii', 'ignore').decode('ascii')
    if not cleaned_url.startswith(('http://', 'https://')):
        cleaned_url = 'http://' + cleaned_url
    return cleaned_url


def get_web_page(src, webdriver):
    cleaned_url = clean_url(src)
    return webdriver.get(cleaned_url)


def search_for_links(driver, url):
    # Navigate to the page
    driver.get(clean_url(url))

    # Get the HTML source of the page
    try:
        html = driver.page_source
    except Exception as e:
        print(e)
        return url

    # Parse the HTML using BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')

    # Search for all links that include specific keywords
    for link in soup.find_all('a', href=True):
        if any(keyword in link.text.lower() for keyword in ['contact', 'connect', 'involve', 'involved']):
            # Return the first matching link
            return link['href']
    return url


def get_contact_link(origin_url, url):
    if not origin_url.startswith('http://') and not origin_url.startswith('https://'):
        origin_url = 'http://' + origin_url

    if url.startswith('http://') or url.startswith('https://') or url.endswith('.com') or url.endswith(
            '.au') or url.endswith('.org'):
        return url

    if origin_url.endswith("/") and url.startswith("/"):
        url = url[1:]
    elif not origin_url.endswith("/") and not url.startswith("/"):
        url = "/" + url

    return origin_url + url


def read_csv(path):
    site_list = []
    with open(path, newline='', encoding='utf-8') as csvfile:
        spamreader = csv.reader(csvfile, delimiter=' ', quotechar='|')
        for row in spamreader:
            site_list.append(', '.join(row))

    return site_list


def json2list(text):
    json.loads(re.findall(r"json\n(.*?)\n", text, re.DOTALL))


def write_to_csv(file_path, data):
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(data)


def query(text, model, site):
    if model == 'gpt':
        answer = ask_gpt(text)
    else:
        answer = ask_gemini(text)
    print(f"{site}: {answer}")
    answer = answer.strip("```json").strip("```").strip().replace('" "', '""').replace('null', '""')
    try:
        # Convert the JSON string into a Python list
        contact_info = json.loads(answer)

        # Ensure it's a valid list and then write to CSV
        if isinstance(contact_info, list) and contact_info:
            contact_info.insert(0, site)
            write_to_csv(write_to_path, contact_info)
        else:
            write_to_csv(write_to_path, [site, "", "", "", ""])
    except json.JSONDecodeError:
        write_to_csv(write_to_path, [site, "", "", "", ""])


if __name__ == '__main__':
    site_list = read_csv("sites.csv")
    webdriver = init_web_driver()
    contact_list = []

    write_to_path = "contacts.csv"
    row = ['site', 'name', 'email', 'phone', 'fax']
    with open(write_to_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(row)

    for site in site_list:
        result = search_for_links(webdriver, site)
        new_link = get_contact_link(site, result)
        webdriver.get(clean_url(new_link))
        web_page = webdriver.page_source
        print(find_contacts(webdriver, site))

        gemini_text = (f"'{web_page}', view these html contents, who can I contact with, if I want to buy meats? If no "
                       f"corresponding information, leave it blank. Show the json only with format: [name, "
                       f"email, phone, fax]")

        gpt_text = (f"View {clean_url(new_link)}, who can I contact with, if I want to buy meats? If no "
                    f"corresponding information, leave it blank. Show the json only with format: "
                    f"[name, email, phone, fax]")

        # for i in range(3):
        #     query(gemini_text, 'gemini', site)

        #query(gemini_text, 'gpt', site)
