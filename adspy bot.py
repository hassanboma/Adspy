"""
🤖 AdSpy Bot - بدون Facebook API Token
=======================================
يعمل عبر scraping مكتبة إعلانات فيسبوك مباشرة

المتطلبات:
    pip install python-telegram-bot requests beautifulsoup4 lxml

الإعداد:
    1. أنشئ بوت من @BotFather واحصل على TOKEN فقط
    2. ضع التوكن في TELEGRAM_TOKEN
"""

import os
import re
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)

# ─── إعدادات ───────────────────────────────────────────────
TELEGRAM_TOKEN = "8706423383:AAGTWTXzlnsgamwzpodxwmjfvAcqhICOW7k"

WAITING_KEYWORD, WAITING_COUNTRY, WAITING_MENU = range(3)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Headers لتجنب الحظر ───────────────────────────────────
HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept-Language": "ar,en-US;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.facebook.com/",
    },
    {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept-Language": "ar-SA,ar;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://www.facebook.com/",
    },
]

COUNTRIES = {
    "SA": "🇸🇦 السعودية",
    "AE": "🇦🇪 الإمارات",
    "EG": "🇪🇬 مصر",
    "MA": "🇲🇦 المغرب",
    "ALL": "🌍 الكل",
}

TRENDING_KEYWORDS = [
    "ساعة ذكية", "عطر رجالي", "كريم تبييض",
    "مكملات رياضية", "إكسسوارات هاتف", "ملابس نسائية",
]


# ─── دوال الجلب والتحليل ──────────────────────────────────

def build_ad_library_url(keyword: str, country: str = "SA") -> str:
    """بناء رابط مكتبة الإعلانات"""
    base = "https://www.facebook.com/ads/library/"
    country_param = "ALL" if country == "ALL" else country
    return (
        f"{base}?active_status=active"
        f"&ad_type=all"
        f"&country={country_param}"
        f"&q={requests.utils.quote(keyword)}"
        f"&search_type=keyword_unordered"
        f"&media_type=all"
    )


def fetch_ads_page(keyword: str, country: str = "SA") -> list:
    """جلب الإعلانات من مكتبة فيسبوك"""
    url = build_ad_library_url(keyword, country)
    headers = random.choice(HEADERS_LIST)

    try:
        session = requests.Session()
        # زيارة الصفحة الرئيسية أولاً
        session.get("https://www.facebook.com/", headers=headers, timeout=10)
        time.sleep(random.uniform(1, 2))

        resp = session.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        ads = parse_ads_from_html(resp.text, keyword, country)
        return ads

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}")
        return []
    except Exception as e:
        logger.error(f"General error: {e}")
        return []


def parse_ads_from_html(html: str, keyword: str, country: str) -> list:
    """تحليل HTML واستخراج بيانات الإعلانات"""
    ads = []
    soup = BeautifulSoup(html, "lxml")

    # استخراج النصوص من الـ meta وعناصر الصفحة
    title = soup.find("title")
    page_title = title.get_text() if title else ""

    # البحث عن عناصر الإعلانات
    ad_elements = (
        soup.find_all("div", {"data-testid": re.compile("ad", re.I)}) or
        soup.find_all("div", class_=re.compile("(x1yztbdb|x1n2onr6|xh8yej3)", re.I)) or
        soup.find_all("div", attrs={"role": "article"})
    )

    # إذا لم يجد عناصر محددة، استخرج ما يتوفر
    if not ad_elements:
        # استخراج نصوص عامة
        all_text_blocks = soup.find_all(["p", "span", "div"], string=re.compile(r'\w{10,}'))
        for i, block in enumerate(all_text_blocks[:8]):
            text = block.get_text(strip=True)
            if len(text) > 30:
                ads.append({
                    "index": i + 1,
                    "page_name": f"صفحة #{i+1}",
                    "body": text[:300],
                    "url": build_ad_library_url(keyword, country),
                    "is_active": True,
                })
        return ads

    for i, el in enumerate(ad_elements[:8]):
        text = el.get_text(separator=" ", strip=True)
        if len(text) < 20:
            continue

        # محاولة استخراج اسم الصفحة
        page_el = (
            el.find("a", href=re.compile(r"facebook\.com/")) or
            el.find(["h2", "h3", "strong"])
        )
        page_name = page_el.get_text(strip=True)[:50] if page_el else f"صفحة #{i+1}"

        ads.append({
            "index": i + 1,
            "page_name": page_name,
            "body": text[:300],
            "url": build_ad_library_url(keyword, country),
            "is_active": True,
        })

    return ads


def analyze_profit(ad: dict, keyword: str) -> dict:
    """تحليل الإعلان وتقدير الربحية بالذكاء الاصطناعي البسيط"""
    body = ad.get("body", "").lower()
    score = 0
    signals = []

    # إشارات الشراء
    buy_signals = ["اشتري", "اطلب", "order", "shop", "buy", "سعر", "خصم", "عرض", "توصيل", "شحن مجاني", "متاح", "متوفر"]
    for s in buy_signals:
        if s in body:
            score += 1
            signals.append(f"✅ {s}")

    # إشارات الإلحاح
    urgency_signals = ["محدود", "آخر", "اليوم فقط", "limited", "last", "only today", "سارع", "لا تفوت"]
    for s in urgency_signals:
        if s in body:
            score += 2
            signals.append(f"🔥 {s}")

    # إشارات الثقة
    trust_signals = ["ضمان", "أصلي", "معتمد", "guarantee", "official", "authentic", "تجربة", "نتائج"]
    for s in trust_signals:
        if s in body:
            score += 1
            signals.append(f"⭐ {s}")

    # طول النص (إعلان مفصّل = جهد أكبر = ربح محتمل أعلى)
    if len(body) > 200:
        score += 2
    elif len(body) > 100:
        score += 1

    # تقييم الربحية
    if score >= 6:
        level = "🔥 مرتفع جداً"
        emoji = "🟢"
        advice = "منتج واعد جداً! المنافس يستثمر فيه بكثافة"
    elif score >= 3:
        level = "⚡ متوسط"
        emoji = "🟡"
        advice = "يستحق الدراسة، جرّب بميزانية صغيرة"
    else:
        level = "💤 منخفض"
        emoji = "🔴"
        advice = "ليس مقنعاً، ابحث عن منتج آخر"

    return {
        "score": score,
        "level": level,
        "emoji": emoji,
        "advice": advice,
        "signals": signals[:4],
    }


def format_ad_card(ad: dict, analysis: dict) -> str:
    """تنسيق بطاقة الإعلان"""
    signals_text = " | ".join(analysis["signals"]) if analysis["signals"] else "لا توجد إشارات واضحة"

    return (
        f"━━━━━━━━━━━━━━━━\n"
        f"📌 *إعلان #{ad['index']}*\n"
        f"🏪 *الصفحة:* {ad['page_name']}\n\n"
        f"📝 *النص:*\n{ad['body'][:250]}...\n\n"
        f"🔍 *إشارات الشراء:*\n{signals_text}\n\n"
        f"{analysis['emoji']} *الربحية: {analysis['level']}*\n"
        f"💡 {analysis['advice']}\n"
        f"\n🔗 [عرض الإعلان على فيسبوك]({ad['url']})"
    )


# ─── هاندلرز البوت ────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔍 بحث بكلمة مفتاحية", callback_data="search")],
        [InlineKeyboardButton("🔥 منتجات رائجة الآن", callback_data="trending")],
        [InlineKeyboardButton("📖 كيف أستخدم البوت؟", callback_data="help")],
    ]
    await update.message.reply_text(
        "🕵️ *مرحباً في AdSpy Bot!*\n\n"
        "أكشف لك المنتجات الرابحة من مكتبة\n"
        "إعلانات فيسبوك مباشرة 💰\n\n"
        "بدون API — بدون توكن فيسبوك ✅\n\n"
        "اختر من القائمة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return WAITING_MENU


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "search":
        await query.message.reply_text(
            "🔍 *ابحث عن منتج*\n\n"
            "أرسل كلمة مفتاحية:\n"
            "مثال: `ساعة ذكية` أو `عطر رجالي`\n"
            "أو `protein` أو `dress`",
            parse_mode="Markdown"
        )
        return WAITING_KEYWORD

    elif query.data == "trending":
        await show_trending(query.message, context)

    elif query.data == "help":
        await query.message.reply_text(
            "📖 *طريقة الاستخدام:*\n\n"
            "1️⃣ اضغط 'بحث بكلمة مفتاحية'\n"
            "2️⃣ أرسل اسم المنتج\n"
            "3️⃣ اختر الدولة\n"
            "4️⃣ شوف التحليل والربحية\n\n"
            "🟢 *ربحية مرتفعة* = المنافس يكسب منه\n"
            "🟡 *ربحية متوسطة* = يستحق التجربة\n"
            "🔴 *ربحية منخفضة* = تجنّبه\n\n"
            "💡 *سر النجاح:*\n"
            "ابحث عن منتج فيه إعلانات كثيرة\n"
            "= دليل أن الناس تشتريه ✅",
            parse_mode="Markdown"
        )

    return WAITING_MENU


async def receive_keyword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyword = update.message.text.strip()
    context.user_data["keyword"] = keyword

    keyboard = [
        [
            InlineKeyboardButton("🇸🇦 السعودية", callback_data="c_SA"),
            InlineKeyboardButton("🇦🇪 الإمارات", callback_data="c_AE"),
        ],
        [
            InlineKeyboardButton("🇪🇬 مصر", callback_data="c_EG"),
            InlineKeyboardButton("🇲🇦 المغرب", callback_data="c_MA"),
        ],
        [InlineKeyboardButton("🌍 كل الدول", callback_data="c_ALL")],
    ]
    await update.message.reply_text(
        f"✅ البحث عن: *{keyword}*\n\nاختر الدولة:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return WAITING_COUNTRY


async def receive_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    country_code = query.data.replace("c_", "")
    country_name = COUNTRIES.get(country_code, "🌍")
    keyword = context.user_data.get("keyword", "")

    msg = await query.message.reply_text(
        f"⏳ جاري البحث عن *{keyword}* في {country_name}...\n"
        f"يرجى الانتظار 🔍",
        parse_mode="Markdown"
    )

    ads = fetch_ads_page(keyword, country_code)

    if not ads:
        await msg.edit_text(
            "⚠️ *لم أجد نتائج*\n\n"
            "جرّب:\n"
            "• كلمة أقصر\n"
            "• اللغة الإنجليزية\n"
            "• دولة مختلفة\n\n"
            "أو افتح الرابط مباشرة:\n"
            f"{build_ad_library_url(keyword, country_code)}",
            parse_mode="Markdown"
        )
        return WAITING_MENU

    # تحليل الإعلانات
    analyses = [analyze_profit(ad, keyword) for ad in ads]
    high = sum(1 for a in analyses if a["score"] >= 6)
    med = sum(1 for a in analyses if 3 <= a["score"] < 6)

    await msg.edit_text(
        f"📊 *نتائج: {keyword} — {country_name}*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📦 إعلانات وجدتها: `{len(ads)}`\n"
        f"🟢 ربحية عالية: `{high}`\n"
        f"🟡 ربحية متوسطة: `{med}`\n"
        f"━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )

    # إرسال تفاصيل كل إعلان
    for ad, analysis in zip(ads, analyses):
        card = format_ad_card(ad, analysis)
        try:
            await query.message.reply_text(
                card,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"Error sending card: {e}")

    # توصية نهائية
    best = max(analyses, key=lambda a: a["score"]) if analyses else None
    if best and best["score"] >= 3:
        await query.message.reply_text(
            f"🎯 *توصية البوت:*\n\n"
            f"المنتج *{keyword}* يبدو واعداً!\n"
            f"ابدأ بميزانية صغيرة واختبر السوق 💪\n\n"
            f"🔗 *رابط مكتبة الإعلانات الكاملة:*\n"
            f"{build_ad_library_url(keyword, country_code)}",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

    return WAITING_MENU


async def show_trending(message, context):
    """عرض المنتجات الرائجة"""
    await message.reply_text("⏳ جاري تحليل المنتجات الرائجة...")

    results = []
    for kw in TRENDING_KEYWORDS[:4]:
        ads = fetch_ads_page(kw, "SA")
        if ads:
            analyses = [analyze_profit(ad, kw) for ad in ads]
            high = sum(1 for a in analyses if a["score"] >= 6)
            total_score = sum(a["score"] for a in analyses)
            results.append((kw, len(ads), high, total_score))
        time.sleep(1)

    if not results:
        await message.reply_text("❌ تعذّر جلب البيانات، حاول لاحقاً")
        return

    results.sort(key=lambda x: x[3], reverse=True)

    msg = "🔥 *أكثر المنتجات ربحية الآن:*\n━━━━━━━━━━━━━━━━\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    for i, (kw, total, high, score) in enumerate(results):
        bar = "🟩" * min(high, 5) + "⬜" * (5 - min(high, 5))
        msg += (
            f"{medals[i]} *{kw}*\n"
            f"   {bar}\n"
            f"   إعلانات: {total} | ربحية عالية: {high}\n\n"
        )

    msg += "💡 اضغط 'بحث' للتعمق في أي منتج"
    await message.reply_text(msg, parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء. أرسل /start للبدء")
    return ConversationHandler.END


# ─── تشغيل البوت ──────────────────────────────────────────

import asyncio

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(button_handler, pattern="^(search|trending|help)$"),
        ],
        states={
            WAITING_MENU: [
                CallbackQueryHandler(button_handler, pattern="^(search|trending|help)$")
            ],
            WAITING_KEYWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_keyword)
            ],
            WAITING_COUNTRY: [
                CallbackQueryHandler(receive_country, pattern="^c_")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)

    print("🤖 AdSpy Bot يعمل الآن بدون Facebook Token...")
    app.run_polling()


if __name__ == "__main__":
    main()
