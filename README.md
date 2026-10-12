# 🚀 Exness SMC 1-Hour Order Block Telegram Bot

২৪/৭ ক্লাউডে স্বয়ংক্রিয়ভাবে বিটকয়েন (BTCUSD) ১-ঘণ্টার অর্ডার ব্লক স্ক্যান করার এবং এক্সনেস (Exness) লট সাইজ সহ টেলিগ্রামে লাইভ এন্ট্রি ও স্টপ লস অ্যালার্ট পাঠানোর প্রোডাকশন রেডি বট।

---

## 📁 ফাইল পরিচিতি:
* `app.py` - মূল বট ইঞ্জিন + ক্লাউড হেলথ চেক ওয়েব সার্ভার।
* `requirements.txt` - ক্লাউড লাইব্রেরি লিস্ট (`Flask`, `requests`, `gunicorn`)।
* `Procfile` - রেন্ডার ওয়েব সার্ভিসের স্টার্ট কমান্ড।
* `render.yaml` - রেন্ডার অটো-কনফিগারেশন ব্লুপ্রিন্ট।

---

## 🛠️ GitHub এবং Render-এ হোস্ট করার সহজ গাইড (Step-by-Step):

### ধাপ ১: GitHub-এ কোড আপলোড করা
1. [GitHub.com](https://github.com)-এ লগইন করে **"New Repository"**-তে ক্লিক করুন।
2. রিপোজিটরির নাম দিন: `exness-smc-telegram-bot` (Public বা Private রাখতে পারেন)।
3. আপনার পিসির এই ফোল্ডার (`C:\Users\Ashraf\.gemini\antigravity\scratch\Exness_SMC_Telegram_Bot`)-এ কমান্ড প্রম্পট বা গিট ব্যাশ খুলে নিচের কমান্ডগুলো দিন:
   ```bash
   git init
   git add .
   git commit -m "Initial commit of SMC Telegram Bot"
   git branch -M main
   git remote add origin https://github.com/আপনার_ইউজারনেম/exness-smc-telegram-bot.git
   git push -u origin main
   ```
   *(অথবা GitHub ওয়েবসাইটে সরাসরি গিয়ে "Upload files" দিয়ে এই ফোল্ডারের ফাইলগুলো টেনে ছেড়ে দিন।)*

---

### ধাপ ২: Render.com-এ ফ্রি হোস্টিং সেটআপ
1. [Render.com](https://render.com)-এ ফ্রি একাউন্ট খুলুন (GitHub দিয়ে সাইন ইন করা সবচেয়ে সহজ)।
2. ড্যাশবোর্ডে **"New +"** বাটনে ক্লিক করে **"Web Service"** সিলেক্ট করুন।
3. আপনার গিটহাব রিপোজিটরিটি (`exness-smc-telegram-bot`) কানেক্ট করুন।
4. সেটিংস পূরণ করুন:
   * **Name:** `exness-smc-bot`
   * **Region:** Singapore বা Frankfurt
   * **Branch:** `main`
   * **Runtime:** `Python 3`
   * **Build Command:** `pip install -r requirements.txt`
   * **Start Command:** `gunicorn app:app`
   * **Instance Type:** `Free` (বিনামূল্যে)
5. **Environment Variables (ঐচ্ছিক, কোডে ডিফল্ট বসানো আছে):**
   * `TELEGRAM_BOT_TOKEN` = `8995620553:AAHAyY1lOSruZUOx-sWjtQPXBZc-55j0Cjo`
   * `TELEGRAM_CHAT_ID` = `7736288854`
6. নিচে **"Create Web Service"** বাটনে ক্লিক করুন!

কয়েক মিনিটের মধ্যে রেন্ডার স্বয়ংক্রিয়ভাবে বটটি লাইভ করে দেবে এবং আপনাকে একটি ফ্রি লাইভ লিঙ্ক দেবে (যেমন: `https://exness-smc-bot.onrender.com`)।

---

### ধাপ ৩: বট যেন কখনো ঘুমিয়ে না পড়ে (24/7 Always Awake ট্রিক)
রেন্ডারের ফ্রি সার্ভার ১৫ মিনিট কোনো ভিজিটর না থাকলে স্লিপে চলে যায়। এটি ২৪/৭ সার্বক্ষণিক সজাগ রাখার উপায়:
1. [Cron-job.org](https://cron-job.org) অথবা [UptimeRobot.com](https://uptimerobot.com)-এ একটি ফ্রি একাউন্ট খুলুন।
2. একটি নতুন মনিটর যোগ করুন:
   * URL: `https://আপনার-রেন্ডার-নাম.onrender.com/health`
   * Interval: **Every 5 minutes (প্রতি ৫ মিনিট পর পর)**
3. ব্যাস! ক্রন-জব প্রতি ৫ মিনিটে আপনার বটের লিঙ্কে পিং করবে, ফলে সার্ভার কখনোই স্লিপে যাবে না এবং আপনি প্রতি ১-ঘণ্টা ক্যান্ডেল ক্লোজে সঠিক সময়ে নোটিশ পেতে থাকবেন!
