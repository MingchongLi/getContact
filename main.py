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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


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
        model="gpt-4o-mini",
        max_tokens=500
    )
    print(f"token used: {chat_completion.usage.total_tokens}")
    return chat_completion.choices[0].message.content


def get_context(parent_element):
    try:
        # Retrieve and clean up the context text
        context_text = parent_element.get_attribute("innerText")
        context_text = "\n".join(line.strip() for line in context_text.splitlines() if line.strip())
        return context_text
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def clear_dict(contacts_dict, depth_limit):
    filtered_contacts = {}
    for contact, occurrences in contacts_dict.items():
        # Group elements by depth
        grouped_by_depth = {}
        for occurrence in occurrences:
            depth = occurrence['depth']
            if depth not in grouped_by_depth:
                grouped_by_depth[depth] = []
            grouped_by_depth[depth].append(occurrence['element'])

        # Sort depth levels by greatest depth first
        sorted_depths = sorted(grouped_by_depth.keys(), reverse=True)

        # Collect distinct elements until we reach the nth one (defined by depth_limit)
        distinct_elements = []
        for depth in sorted_depths:
            for element in grouped_by_depth[depth]:
                if element not in distinct_elements:  # Avoid duplicates
                    distinct_elements.append(element)
                if len(distinct_elements) == depth_limit:
                    # Once we have reached the depth_limit, stop
                    filtered_contacts[contact] = {
                        'element': distinct_elements[-1],
                        'depth': depth
                    }
                    break
            if len(distinct_elements) == depth_limit:
                break

        # If fewer distinct elements than the limit, keep the last one available
        if len(distinct_elements) < depth_limit and distinct_elements:
            filtered_contacts[contact] = {
                'element': distinct_elements[-1],
                'depth': occurrences[-1]['depth']
            }

    return filtered_contacts

def is_js_code(text):
    # Define common JavaScript patterns
    js_patterns = [
        r'\bfunction\b', r'\bvar\b', r'\blet\b', r'\bconst\b',
        r'\bif\b', r'\belse\b', r'\breturn\b', r'console\.log',
        r'\bfor\b', r'\bwhile\b', r'\bdo\b', r'==', r'===', r'\('
    ]

    # Check if any of the patterns are found in the text
    for pattern in js_patterns:
        if re.search(pattern, text):
            return True
    return False

# Function to check if more than 50% of the strings are JavaScript code
def detect_js_strings(strings):
    js_count = sum(1 for string in strings if is_js_code(string))
    return js_count > (len(strings) / 2)

def find_contacts(browser_driver, site):
    contact_list = []

    # Regex pattern for emails
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}'
    #phone_pattern = r"\+61\s?\(?0?\d{1,2}\)?[\s.-]?\d{4}[\s.-]?\d{4}"
    australian_phone_regex = re.compile(r'''
    (
        (\+61\s?\(0\)|\+61\s?|0)?
        [\s\-\.]?
        (\d{1,2})?
        [\s\-\.]?
        \d{1,4}
        [\s\-\.]?
        \d{3,4}
        [\s\-\.]?
        \d{3,4}
    )
    ''', re.VERBOSE)

    elements = browser_driver.find_elements(By.XPATH, "//*")

    email_contacts = {}
    phone_contacts = {}

    for element in elements:
        try:
            text = element.get_attribute("innerText")
        except Exception as e:
            print(e)
            continue

        parent_count = 0
        current_element = element

        while current_element.tag_name.lower() != 'html':
            # Move to the parent element
            current_element = current_element.find_element(By.XPATH, "./..")
            parent_count += 1
        if text and re.search(email_pattern, text):
            emails = re.findall(email_pattern, text, re.IGNORECASE)
            for email in emails:
                email = str(email)
                if email in email_contacts:
                    email_contacts[email].append({
                        'element': element,
                        'depth': parent_count
                    })
                else:
                    email_contacts[email] = [{
                        'element': element,
                        'depth': parent_count
                    }]

        if text and australian_phone_regex.search(text):
            phones = australian_phone_regex.findall(text)
            for phone in phones:
                phone = str(phone[0]).replace('\\xa', '').strip()
                if phone in phone_contacts:
                    phone_contacts[phone].append({
                        'element': element,
                        'depth': parent_count
                    })
                else:
                    phone_contacts[phone] = [{
                        'element': element,
                        'depth': parent_count
                    }]
    email_contacts = clear_dict(email_contacts, 4)
    phone_contacts = clear_dict(phone_contacts, 4)
    for element in email_contacts:
        context = get_context(email_contacts[element]['element'])
        if detect_js_strings(context):
            contact_list.append([element, 'N'])
        else:
            answer = ask_gpt(
                f"\"{context}\"\nIf I want to buy beef, can I contact {element}? If so, what is their name and number? "
                f"Answer by the format: [Y/N, name, number, email]. Only answer an array.")
            contact_list.append([element, answer])
    for element in phone_contacts:
        context = get_context(phone_contacts[element]['element'])
        if detect_js_strings(context):
            contact_list.append([element, 'N'])
        else:
            answer = ask_gpt(
                f"\"{context}\"\nIf I want to buy beef, can I contact {element}? If so, what is their name and "
                f"email? Answer by the format: [Y/N, name, email, email]. Only answer an array.")
            contact_list.append([element, answer])

    return contact_list


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
    try:
        # Navigate to the page
        driver.get(clean_url(url))

        # Get the HTML source of the page
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
    return answer


def append2csv(write_to_path, answer):
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
    for site in site_list:
        result = search_for_links(webdriver, site)
        new_link = get_contact_link(site, result)
        webdriver.get(clean_url(new_link))
        web_page = webdriver.page_source

        contact = find_contacts(webdriver, site)
        for entry in contact:
            write_to_csv(write_to_path, contact)
