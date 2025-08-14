# sct-huginnmuninn  
**Social Climate Tech – SocialLab AI News Summarizer**

---

## Who Are Huginn & Muninn?  
In Norse mythology, **Huginn** (“thought”) and **Muninn** (“memory”) are Odin’s two ravens.  
Each day, they fly across the world (Midgard), gathering information and returning it to Odin.  

In this project, Huginn & Muninn work for **Social Climate Tech**. Twice a day, they fetch the latest headlines from trusted news sites, run them through AI, and return them with **two distinct perspectives**:  

1. **For the people** – plain-language summaries focused on what matters for everyday lives.  
2. **For the politics** – analysis of political motives, strategies, and behind-the-scenes dynamics.  

This is part of the [SocialLab](https://socialclimate.tech/sociallab), our collaborative education program exploring civic awareness and climate-conscious tech.

---

## Features
- **Dual-perspective AI summaries**: one from the people’s view, one from the political view.
- **Two AI options**:
  - **OpenAI API** – use `gpt-4` (or another model) via your API key.
  - **Ollama** – run LLaMA or other local models for a fully offline experience.
- **Runs automatically twice a day** using cron (Mac/Linux) or Task Scheduler (Windows).
- **Email delivery** of summaries via Gmail.
- **Easy customization** of scraping targets, prompts, and output.

---

## Repository Structure

```bash
│
├── README.md ← This file
├── CONTRIBUTORS.md ← Credits and contributors
├── ETHICS.md ← Our stance on scraping, AI bias, and responsible use
├── config.example.json ← Example configuration
├── config.json ← Your local config (not committed)
├── main.py ← The Huginn & Muninn script
└── requirements.txt ← Python dependencies
```


## Setup

### Clone the repo
```bash
   git clone https://github.com/yourusername/sct-huginnmuninn.git
   cd sct-huginnmuninn
   pip install -r requirements.txt
```

Copy config.example.json to config.json and update your values:

```bash
   cp config.example.json config.json

      {
          "openai_api_key": "YOUR_OPENAI_API_KEY",
          "email": "your.email@gmail.com",
          "app_password": "your_gmail_app_password",
          "use_openai": true,
          "ollama_base_url": "http://localhost:11434"
      }
```

use_openai – set to true for OpenAI, false for Ollama.

ollama_base_url – default for local Ollama install.

Gmail App Passwords: You need to enable 2FA and generate an App Password in Google Account Security settings.

## Using Ollama Locally (Offline Mode)

Ollama lets you run large language models completely on your machine.

Install Ollama: https://ollama.ai

Pull a model (example with LLaMA 3.2):

```bash
ollama pull llama3.2
```

Start Ollama (it usually runs at http://localhost:11434).

Set "use_openai": false in config.json.

How the Script Works

Scraping headlines – The script visits a curated list of news sites and collects top article links.
We find the correct HTML tags using Chrome DevTools:

Right-click → Inspect → hover over elements to find containers (div, section, etc.).

Copy the selector or class name to adjust the scraper logic.

Respecting access rules – We never bypass paywalls; we only use freely available public content.

Summarization & analysis – Articles are fed into the AI prompt:

```python
prompt = (
    "Read the following article and do two things:\n"
    "1. Summarize it from the perspective of what is best for ordinary people, avoiding political spin.\n"
    "2. Analyze why the politicians made their statements, considering party strategy, internal dynamics, "
    "and public opinion.\n"
    "Keep the answer structured with clear bullet points and headings."
)

```
You can edit this prompt in daily_news_analysis.py to suit your own needs.

Email delivery – The script compiles all summaries and emails them to you.

## Running Automatically
Mac / Linux – cronjob

Edit crontab:
```bash
crontab -e
```
Add:
```bash
0 8,20 * * * /usr/bin/python3 /path/to/sct-huginnmuninn/daily_news_analysis.py
```

This runs at 08:00 and 20:00 every day.

Windows – Task Scheduler

Open Task Scheduler.

Create a new basic task.

Set triggers for morning and evening.

Action: run python with the full path to daily_news_analysis.py.

## Customization

News sources – edit the news_sites list in daily_news_analysis.py.

Prompt style – tweak the prompt variable.

Email recipients – change the send_email function.

Model choice – swap OpenAI models (gpt-4, gpt-3.5) or Ollama models.

## Contributing

See CONTRIBUTING.md for guidelines.

## Ethics

We believe in responsible scraping:

Only collect public information.

Avoid paywalled or private data.

Be transparent about AI bias and sources.
Read more in ETHICS.md.

## Links

Social Climate Tech - https://socialclimate.tech/

Social Climate Tech SocialLab - https://socialclimate.tech/sociallab
