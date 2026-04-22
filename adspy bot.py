"""
🤖 AdSpy Bot - نسخة محسّنة
"""

import os
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "ضع_توكن_هنا")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COUNTRIES = {
    "SA": "🇸🇦 السعودية",
    "AE": "🇦🇪 الإمارات",
    "EG": "🇪🇬 مصر",
    "ALL": "🌍 الكل",
}


def build_url(keyword, country="SA"):
    return (
        f"https://www.facebook.com/ads/library/"
        f"?active_status=active&ad_type=all"
        f"&country={country}"
        f"&q={requests.utils.quote(keyword)}"
        f"&search_type=keyword_unordered"
    )


def analyze(text):
    text = text.lower()
    score = 0
    buy_words = ["اشتري", "اطلب", "order", "buy", "shop", "سعر", "خصم", "عرض", "توصيل", "شحن"]
    urgent_words = ["محدود", "اليوم فقط", "limited", "only today", "سارع", "لا تفوت"]
    for w in buy_words:
        if w in text: score += 1
    for w in urgent_words:
        if w in text: score += 2
    if len(text) > 150: score += 1
    if score >= 5:
        return "🟢 ربحية مرتفعة"
    elif score >= 2:
        return "🟡 ربحية متوسطة"
    else:
        return "🔴 ربحية منخفضة"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 بحث عن منتج", callback_data="menu_search")],
        [InlineKeyboardButton("🔥 منتجات رائجة", callback_data="menu_trending")],
        [InlineKeyboardButton("📖 كيف أستخدم البوت؟", callback_data="menu_help")],
    ]
    text = (
        "🕵️ *مرحباً في AdSpy Bot!*\n\n"
        "اكتشف المنتجات الرابحة من\n"
        "مكتبة إعلانات فيسبوك 💰\n\n"
        "اختر من القائمة:"
    )
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu_search":
        context.user_data["state"] = "waiting_keyword"
        await query.message.reply_text(
            "🔍 أرسل اسم المنتج الذي تريد البحث عنه\n\n"
            "مثال: `ساعة ذكية` أو `عطر رجالي`",
            parse_mode="Markdown"
        )

    elif data == "menu_help":
        await query.message.reply_text(
            "📖 *طريقة الاستخدام:*\n\n"
            "1️⃣ اضغط 'بحث عن منتج'\n"
            "2️⃣ أرسل اسم المنتج\n"
            "3️⃣ اختر الدولة\n"
            "4️⃣ شوف التحليل\n\n"
            "🟢 ربحية مرتفعة = المنافس يكسب منه\n"
            "🟡 ربحية متوسطة = يستحق التجربة\n"
            "🔴 ربحية منخفضة = تجنّبه",
            parse_mode="Markdown"
        )

    elif data == "menu_trending":
        await query.message.reply_text("⏳ جاري البحث عن المنتجات الرائجة...")
        keywords = ["ساعة ذكية", "عطر رجالي", "مكملات رياضية", "إكسسوارات"]
        msg = "🔥 *المنتجات الرائجة:*\n━━━━━━━━━━━━\n\n"
        for kw in keywords:
            url = build_url(kw, "SA")
            msg += f"🏷 *{kw}*\n🔗 [بحث في فيسبوك]({url})\n\n"
        await query.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

    elif data == "menu_back":
        await start(update, context)

    elif data.startswith("country_"):
        country = data.replace("country_", "")
        keyword = context.user_data.get("keyword", "")
        country_name = COUNTRIES.get(country, "🌍")

        if not keyword:
            await query.message.reply_text("❌ حدث خطأ، أرسل /start وابدأ من جديد")
            return

        await query.message.reply_text(f"⏳ جاري البحث عن *{keyword}* في {country_name}...", parse_mode="Markdown")

        url = build_url(keyword, country)

        try:
            headers = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"}
            resp = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, "lxml")
            texts = [el.get_text(strip=True) for el in soup.find_all(["p", "span"], string=True) if len(el.get_text(strip=True)) > 40][:5]
        except Exception as e:
            logger.error(e)
            texts = []

        if texts:
            msg = f"📊 *نتائج: {keyword} — {country_name}*\n━━━━━━━━━━━━\n\n"
            for i, t in enumerate(texts, 1):
                profit = analyze(t)
                msg += f"📌 *إعلان #{i}*\n{t[:200]}\n{profit}\n\n"
        else:
            msg = (
                f"⚠️ لم أجد نصوص مباشرة\n\n"
                f"🔗 شاهد الإعلانات على فيسبوك:\n{url}"
            )

        keyboard = [[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="menu_back")]]
        await query.message.reply_text(
            msg, parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data["state"] = None


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    if state == "waiting_keyword":
        keyword = update.message.text.strip()
        context.user_data["keyword"] = keyword
        context.user_data["state"] = "waiting_country"
        keyboard = [
            [
                InlineKeyboardButton("🇸🇦 السعودية", callback_data="country_SA"),
                InlineKeyboardButton("🇦🇪 الإمارات", callback_data="country_AE"),
            ],
            [
                InlineKeyboardButton("🇪🇬 مصر", callback_data="country_EG"),
                InlineKeyboardButton("🌍 الكل", callback_data="country_ALL"),
            ],
        ]
        await update.message.reply_text(
            f"✅ البحث عن: *{keyword}*\n\nاختر الدولة:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await start(update, context)


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("🤖 AdSpy Bot يعمل الآن...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
