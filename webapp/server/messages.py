"""Ready-to-send heat messages for seniors in English, Chinese, Malay and Tamil (pure functions, unit-tested).

Every sentence is a fixed, hand-written translation of the HeatGuard rulebook, so a message never contains facts or advice the
rulebook doesn't give, and the same situation always produces the same wording. Only the day, the centre and the nearest cool place
are filled in. Place and area names stay in English, as on Singapore signage.

Translations should still be reviewed by native speakers before real use (see docs/decision-log.md).
"""
from __future__ import annotations

import datetime as dt

LANGUAGES = {"en": "English", "zh": "中文", "ms": "Bahasa Melayu", "ta": "தமிழ்"}
ALL_ORDER = ("en", "zh", "ms", "ta")          # one message with all four official languages, in this order
LEVELS = ("very_hot", "hot", "normal")

# ------------------------------------------------------------------------------------------------ dates
_WEEKDAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "zh": ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"],
    "ms": ["Isnin", "Selasa", "Rabu", "Khamis", "Jumaat", "Sabtu", "Ahad"],
    "ta": ["திங்கள்கிழமை", "செவ்வாய்க்கிழமை", "புதன்கிழமை", "வியாழக்கிழமை", "வெள்ளிக்கிழமை", "சனிக்கிழமை", "ஞாயிற்றுக்கிழமை"],
}
_MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "ms": ["Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai", "Ogos", "September", "Oktober", "November", "Disember"],
    "ta": ["ஜனவரி", "பிப்ரவரி", "மார்ச்", "ஏப்ரல்", "மே", "ஜூன்", "ஜூலை", "ஆகஸ்ட்", "செப்டம்பர்", "அக்டோபர்", "நவம்பர்", "டிசம்பர்"],
}
_RELATIVE = {"en": ("Today", "Tomorrow"), "zh": ("今天", "明天"), "ms": ("Hari ini", "Esok"), "ta": ("இன்று", "நாளை")}


def date_text(day: dt.date, lang: str) -> str:
    wd = _WEEKDAYS[lang][day.weekday()]
    if lang == "zh":
        return f"{day.month}月{day.day}日（{wd}）"
    if lang == "en":
        return f"{wd} {day.day} {_MONTHS['en'][day.month - 1]}"
    if lang == "ms":
        return f"{wd}, {day.day} {_MONTHS['ms'][day.month - 1]}"
    return f"{_MONTHS['ta'][day.month - 1]} {day.day}, {wd}"


def when_text(day: dt.date, today: dt.date, lang: str) -> str:
    """'Tomorrow, Tuesday 20 October' / '明天（10月20日，星期二）' / 'Esok (Selasa, 20 Oktober)' — or just the date."""
    rel = {0: _RELATIVE[lang][0], 1: _RELATIVE[lang][1]}.get((day - today).days)
    if lang == "zh":
        d = f"{day.month}月{day.day}日，{_WEEKDAYS['zh'][day.weekday()]}"
        return f"{rel}（{d}）" if rel else d
    d = date_text(day, lang)
    if not rel:
        return d
    return f"{rel}, {d}" if lang == "en" else f"{rel} ({d})"


# ------------------------------------------------------------------------------------------------ seniors
_SENIORS = {
    "en": {
        "hello": "Hello from {centre}!",
        "very_hot": "{when}, the afternoon may be very hot.",
        "hot": "{when}, the afternoon will be hot.",
        "normal": "{when}, the weather looks normal. Have a good day, and drink enough water.",
        "very_hot_steps": ["Stay indoors from 11 am to 4 pm if you can.", "Drink water often, even if you are not thirsty.",
                           "If your home gets too hot, come to {cool}. It is free and air-conditioned."],
        "hot_steps": ["Avoid going out from 12 pm to 4 pm.", "Drink water often.",
                      "If your home gets too hot, come to {cool}. It is free and air-conditioned."],
        "haze": "The haze is unhealthy: keep your windows closed and spend less time outdoors. If you have heart or lung problems, keep your medicine with you.",
        "unwell": "If you feel dizzy or unwell, rest in a cool place and call your family or us.",
        "bye": "Take care!",
    },
    "zh": {
        "hello": "{centre} 问候您！",
        "very_hot": "{when}下午可能会非常炎热。",
        "hot": "{when}下午会比较炎热。",
        "normal": "{when}天气正常。祝您有愉快的一天，记得多喝水。",
        "very_hot_steps": ["上午11点到下午4点，请尽量留在家里。", "即使不口渴，也要经常喝水。",
                           "如果家里太热，可以到 {cool} 休息。那里免费，而且有冷气。"],
        "hot_steps": ["中午12点到下午4点，请尽量不要外出。", "要经常喝水。",
                      "如果家里太热，可以到 {cool} 休息。那里免费，而且有冷气。"],
        "haze": "烟雾指数处于不健康水平：请关好窗户，减少户外活动。如果您有心脏或肺部疾病，请随身携带药物。",
        "unwell": "如果感到头晕或身体不适，请到凉快的地方休息，并联系家人或我们。",
        "bye": "请多保重！",
    },
    "ms": {
        "hello": "Salam sejahtera dari {centre}!",
        "very_hot": "{when}, cuaca petang mungkin sangat panas.",
        "hot": "{when}, cuaca petang akan panas.",
        "normal": "{when}, cuaca dijangka biasa. Semoga hari anda baik, dan minumlah air secukupnya.",
        "very_hot_steps": ["Jika boleh, duduk di dalam rumah dari pukul 11 pagi hingga 4 petang.", "Minum air dengan kerap, walaupun tidak dahaga.",
                           "Jika rumah anda terlalu panas, datanglah ke {cool}. Tempat itu percuma dan berhawa dingin."],
        "hot_steps": ["Elakkan keluar rumah dari pukul 12 tengah hari hingga 4 petang.", "Minum air dengan kerap.",
                      "Jika rumah anda terlalu panas, datanglah ke {cool}. Tempat itu percuma dan berhawa dingin."],
        "haze": "Jerebu berada pada tahap tidak sihat: tutup tingkap dan kurangkan masa di luar rumah. Jika anda ada masalah jantung atau paru-paru, bawa ubat anda bersama.",
        "unwell": "Jika anda rasa pening atau tidak sihat, berehat di tempat yang sejuk dan hubungi keluarga anda atau kami.",
        "bye": "Jaga diri!",
    },
    "ta": {
        "hello": "{centre} சார்பில் வணக்கம்!",
        "very_hot": "{when} மதியம் மிகவும் வெப்பமாக இருக்கலாம்.",
        "hot": "{when} மதியம் வெப்பமாக இருக்கும்.",
        "normal": "{when} வானிலை வழக்கம் போல் இருக்கும். இனிய நாளாக அமையட்டும்; போதுமான அளவு தண்ணீர் குடியுங்கள்.",
        "very_hot_steps": ["முடிந்தால், காலை 11 மணி முதல் மாலை 4 மணி வரை வீட்டிற்குள்ளேயே இருங்கள்.", "தாகம் இல்லாவிட்டாலும், அடிக்கடி தண்ணீர் குடியுங்கள்.",
                           "உங்கள் வீடு மிகவும் சூடாக இருந்தால், {cool}-க்கு வாருங்கள். அங்கு அனுமதி இலவசம்; குளிர்சாதன வசதியும் உண்டு."],
        "hot_steps": ["மதியம் 12 மணி முதல் மாலை 4 மணி வரை வெளியே செல்வதைத் தவிர்க்கவும்.", "அடிக்கடி தண்ணீர் குடியுங்கள்.",
                      "உங்கள் வீடு மிகவும் சூடாக இருந்தால், {cool}-க்கு வாருங்கள். அங்கு அனுமதி இலவசம்; குளிர்சாதன வசதியும் உண்டு."],
        "haze": "புகைமூட்டம் உடல்நலத்திற்குக் கேடான அளவில் உள்ளது: ஜன்னல்களை மூடி வையுங்கள்; வெளியே இருக்கும் நேரத்தைக் குறையுங்கள். இதயம் அல்லது நுரையீரல் பிரச்சினை இருந்தால், உங்கள் மருந்துகளை உடன் வைத்திருங்கள்.",
        "unwell": "தலைசுற்றல் அல்லது உடல்நலக் குறைவு இருந்தால், குளிர்ந்த இடத்தில் ஓய்வெடுத்து, உங்கள் குடும்பத்தினரையோ எங்களையோ தொடர்பு கொள்ளுங்கள்.",
        "bye": "கவனமாக இருங்கள்!",
    },
}

class MessageError(ValueError):
    pass


def compose(*, level: str, day: dt.date, today: dt.date, language: str, centre: str, cool: str | None, haze: bool = False) -> str:
    """The message for one centre and day. `level` is the centre plan's level (very_hot / hot / normal)."""
    if language not in LANGUAGES:
        raise MessageError("Please choose English, 中文, Bahasa Melayu or தமிழ்.")
    if level not in LEVELS:
        raise MessageError("Unknown heat level.")
    centre = (centre or "").strip() or {"en": "your centre", "zh": "您的中心", "ms": "pusat anda", "ta": "உங்கள் மையம்"}[language]
    cool = (cool or "").strip() or {"en": "the nearest Community Club", "zh": "最近的民众俱乐部", "ms": "Kelab Masyarakat yang terdekat",
                                    "ta": "அருகிலுள்ள சமூக மன்றம்"}[language]
    when = when_text(day, today, language)
    return _seniors(language, level, when, centre, cool, haze)


def compose_all(**kwargs) -> str:
    """The same message in English, Chinese, Malay and Tamil, one after another, separated by a blank line."""
    return "\n\n".join(compose(language=lang, **kwargs) for lang in ALL_ORDER)


def _seniors(lang, level, when, centre, cool, haze):
    t = _SENIORS[lang]
    lines = [t["hello"].format(centre=centre), t[level].format(when=when)]
    steps = [s.format(cool=cool) for s in t.get(f"{level}_steps", [])]
    if haze:
        steps.append(t["haze"])
    if level != "normal":
        steps.append(t["unwell"])
    lines += [f"• {s}" for s in steps]
    lines.append(t["bye"])
    return "\n".join(lines)
