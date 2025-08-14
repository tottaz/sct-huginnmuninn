import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import ollama
from urllib.parse import urlparse, urljoin

# === Load config ===
with open("/config/config.json", "r") as f:
    config = json.load(f)

api_key = config.get("openai_api_key")
email = config["email"]
app_password = config["app_password"]
use_openai = config["use_openai"]
ollama_base_url = config["ollama_base_url"]

if not api_key:
    raise ValueError("API key not found in config/config.json")

# Setup OpenAI client
if use_openai:
    client = OpenAI(api_key=api_key)
else:
    # Ollama setup (ensure Ollama is running locally)
    ollama_client = ollama

# === List of news sites ===
news_sites = [
    "https://www.theguardian.com/world",
    "https://www.theguardian.com/world/europe-news",
    "https://www.aftonbladet.se",
    "https://www.expressen.se",
    "https://www.epochtimes.se",
    "https://www.svt.se/"
]


# === Helper function to scrape site ===
def scrape_site(url):
    html = requests.get(url).text
    soup = BeautifulSoup(html, "html.parser")
    headlines = []

    # Scraping logic for The Guardian (using the container-latest-news div)
    if "theguardian" in url:
        latest_news_container = soup.find('div', {'id': 'container-latest-news'})
        if latest_news_container:
            for link in latest_news_container.find_all('a', href=True):
                href = link.get('href')
                if href:
                    headlines.append(href)

    # Scraping logic for Aftonbladet
    elif "aftonbladet" in url:
        main_section = soup.find('section', class_='twocolumnlayout-main_3bf5')
        if main_section:
            for link in main_section.find_all('a', {'data-test-tag': 'internal-link'}):
                href = link.get('href')
                if href:
                    if not href.startswith('http'):
                        href = "https://www.aftonbladet.se" + href
                    headlines.append(href)

    # Scraping logic for Expressen
    elif "expressen" in url:
        for teaser in soup.find_all("div", class_="teaser"):
            anchor = teaser.find("a")
            if anchor and anchor.get("href"):
                headlines.append(anchor["href"])

    # Scraping logic for Epoch Times
    elif "epochtimes" in url:
        for article in soup.find_all("article", class_="groupItem"):
            link = article.find("a", href=True)
            if link:
                href = link.get("href")
                if not href.startswith("http"):
                    href = "https://epochtimes.se" + href
                headlines.append(href)

        # Scraping logic for SVT
    elif "svt.se" in url:
        # Find the div with the class 'LatestNews__contentWrapper___gBmEV'
        latest_news_container = soup.find('div', class_='LatestNews__contentWrapper___gBmEV')

        if latest_news_container:
            # Find all list items <li> and extract the <a> tags with the 'href' attribute
            for item in latest_news_container.find_all('li', class_='LatestNewsItem__root___iB1de'):
                link = item.find('a', href=True)
                if link:
                    href = link.get('href')
                    if href:
                        # Ensure to make the URL absolute if it's relative
                        if not href.startswith('http'):
                            href = "https://www.svt.se" + href
                        headlines.append(href)

    return headlines[:10]  # Return the top 10 links


# === Helper function to summarize and analyze article ===
def summarize_and_analyze_article(article_text, is_swedish=False):
    prompt = (
        "Read the following article and do two things:\n"
        "1. Summarize it from the perspective of what is best for ordinary people, avoiding political spin.\n"
        "2. Analyze why the politicians made their statements, considering party strategy, internal dynamics, "
        "and public opinion.\n"
        "Keep the answer structured with clear bullet points and headings."
    )

    # Add a note if the article is Swedish
    if is_swedish:
        prompt = "This article is in Swedish.\n" + prompt

    if use_openai:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": article_text}
            ]
        )
        return response.choices[0].message.content.strip()

    else:
        # Ollama request via POST method (as per your working setup)
        payload = {
            "model": "llama3.2:latest",  # Use the appropriate model name for Ollama
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": article_text}
            ]
        }

        response = requests.post(
            f"{ollama_base_url}/chat/completions",
            headers={"Content-Type": "application/json"},
            json=payload
        )

        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        else:
            raise Exception(f"Error with Ollama API: {response.text}")


# === Helper function to send email with list of analysis ===
def send_email(subject, body):
    msg = MIMEMultipart()
    msg["From"] = email
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email, app_password)
            server.sendmail(email, email, msg.as_string())
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"Error sending email: {e}")


# === Loop through news sites ===
def process_news():
    all_analyses = []  # Will hold the analyses for all articles

    for site in news_sites:
        print(f"Fetching latest news from {site}...")
        headlines = scrape_site(site)

        for link in headlines:
            if not link.startswith("http"):
                parsed = urlparse(site)
                domain_root = f"{parsed.scheme}://{parsed.netloc}"
                if not link.startswith("/"):
                    link = "/" + link
                link = urljoin(domain_root, link)

            print(f"Processing article: {link}")
            article_html = requests.get(link).text
            article_soup = BeautifulSoup(article_html, "html.parser")
            article_text = " ".join(p.get_text(strip=True) for p in article_soup.find_all("p"))

            # Optional: Limit text size for OpenAI models
            if len(article_text) > 10000:
                article_text = article_text[:10000] + "..."

            # Determine if the site is Swedish
            is_swedish = "svt.se" in site or "aftonbladet.se" in site or "expressen.se" in site

            # Summarize and analyze article
            analysis = summarize_and_analyze_article(article_text, is_swedish=is_swedish)

            # Create a summary entry with link to the full article
            all_analyses.append(f"Article: {link}\nAnalysis:\n{analysis}\n\n")

    # Now send a single email with all analyses
    subject = "Latest News Headlines and Analysis"
    body = "Here are the latest headlines and their analyses:\n\n" + "\n".join(all_analyses)

    # Send the email with all articles' analysis
    send_email(subject, body)
    print("All article analyses sent in one email.")


# Run the news processing and email sending
process_news()
