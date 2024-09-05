from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ.get("OPENAI_KEY"),
)


def get_info(url):
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": f"View {url}, is this a beef supplier/ retailer/ restaurant, who can I contact with? View "
                           f"the contact or connect page if needed. Show me the result enclosing by '[]' and split by "
                           f"',', if not applicable, leave it blank:\n"
                           f"e.g.'[James Adam],[james@meat.au],[12345678]'"
            }
        ],
        model="gpt-4",
        max_tokens=500
    )
    print(f"token used: {chat_completion.usage.total_tokens}")
    print(chat_completion.choices[0].message.content)


if __name__ == '__main__':
    url = "https://mooneypastoralco.com.au/"
    get_info(url)
