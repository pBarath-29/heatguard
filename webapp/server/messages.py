"""Ready-to-send heat messages in English, Chinese, Malay and Tamil (pure functions, unit-tested).

Every sentence is a fixed, hand-written translation of the HeatGuard rulebook, so a message never contains facts or advice the
rulebook doesn't give, and the same situation always produces the same wording. Only the day, the centre, the nearest cool place
and (for staff) the areas to check first are filled in. Place and area names stay in English, as on Singapore signage.

Translations should still be reviewed by native speakers before real use (see docs/decision-log.md).
"""
from __future__ import annotations

import datetime as dt

LANGUAGES = {"en": "English", "zh": "中文", "ms": "Bahasa Melayu", "ta": "தமிழ்"}
AUDIENCES = ("seniors", "staff")
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

# ------------------------------------------------------------------------------------------------ staff
_STAFF = {
    "en": {
        "head": "HeatGuard briefing for {centre} — {when}",
        "very_hot": "Very hot afternoon: high heat stress is possible around the centre, hottest from 12 pm to 4 pm.",
        "hot": "Hot afternoon: moderate heat stress around the centre, hottest from 12 pm to 4 pm.",
        "normal": "Normal afternoon: no heat stress expected.",
        "todo": "To do:",
        "send": "Tonight: send the heat reminder to our seniors.",
        "call_very_hot": "Before 11 am: call or visit seniors who live alone, starting with {focus}.",
        "call_hot": "In the morning: phone seniors who live alone, starting with {focus}.",
        "indoors_very_hot": "12 pm – 4 pm: remind them to stay indoors, drink water often, and come to {cool} if home is too hot.",
        "indoors_hot": "12 pm – 4 pm: remind them to avoid going out and to keep drinking water.",
        "routine": "Routine check-ins. No extra heat steps needed.",
        "haze": "In the morning: check that seniors with heart or lung conditions have their medicine, and remind them to keep windows closed.",
        "and": " and ", "nearby": "our nearby areas",
        "foot": "HeatGuard forecast. On the day, follow NEA's latest advisories.",
    },
    "zh": {
        "head": "HeatGuard 工作简报（{centre}）— {when}",
        "very_hot": "下午非常炎热：中心一带可能出现高度热压力，中午12点到下午4点最热。",
        "hot": "下午炎热：中心一带有中度热压力，中午12点到下午4点最热。",
        "normal": "下午天气正常：预计不会出现热压力。",
        "todo": "待办事项：",
        "send": "今晚：把防暑提醒发给我们的乐龄人士。",
        "call_very_hot": "上午11点前：致电或探访独居的乐龄人士，先从 {focus} 开始。",
        "call_hot": "上午：致电独居的乐龄人士，先从 {focus} 开始。",
        "indoors_very_hot": "中午12点到下午4点：提醒他们留在室内、经常喝水；如果家里太热，可到 {cool} 休息。",
        "indoors_hot": "中午12点到下午4点：提醒他们尽量不要外出，并继续多喝水。",
        "routine": "照常进行例行探访，无需额外防暑措施。",
        "haze": "上午：确认有心脏或肺部疾病的乐龄人士备有药物，并提醒他们关好窗户。",
        "and": "和", "nearby": "附近地区",
        "foot": "以上为 HeatGuard 预测。当天请以 NEA 最新公告为准。",
    },
    "ms": {
        "head": "Taklimat HeatGuard untuk {centre} — {when}",
        "very_hot": "Petang yang sangat panas: tekanan haba yang tinggi mungkin berlaku di sekitar pusat, paling panas dari pukul 12 tengah hari hingga 4 petang.",
        "hot": "Petang yang panas: tekanan haba sederhana di sekitar pusat, paling panas dari pukul 12 tengah hari hingga 4 petang.",
        "normal": "Petang yang biasa: tiada tekanan haba dijangka.",
        "todo": "Tugasan:",
        "send": "Malam ini: hantar peringatan cuaca panas kepada warga emas kita.",
        "call_very_hot": "Sebelum pukul 11 pagi: telefon atau lawat warga emas yang tinggal bersendirian, bermula dengan {focus}.",
        "call_hot": "Pada waktu pagi: telefon warga emas yang tinggal bersendirian, bermula dengan {focus}.",
        "indoors_very_hot": "12 tengah hari – 4 petang: ingatkan mereka supaya duduk di dalam rumah, kerap minum air, dan datang ke {cool} jika rumah terlalu panas.",
        "indoors_hot": "12 tengah hari – 4 petang: ingatkan mereka supaya mengelak keluar rumah dan terus minum air.",
        "routine": "Panggilan dan lawatan biasa. Tiada langkah tambahan untuk cuaca panas.",
        "haze": "Pada waktu pagi: pastikan warga emas yang ada masalah jantung atau paru-paru mempunyai ubat mereka, dan ingatkan mereka supaya menutup tingkap.",
        "and": " dan ", "nearby": "kawasan berdekatan",
        "foot": "Ramalan HeatGuard. Pada hari tersebut, ikut nasihat terkini NEA.",
    },
    "ta": {
        "head": "{centre} — HeatGuard பணிக் குறிப்பு — {when}",
        "very_hot": "மிகவும் வெப்பமான மதியம்: மையத்தைச் சுற்றி அதிக வெப்ப அழுத்தம் ஏற்படலாம்; மதியம் 12 முதல் மாலை 4 மணி வரை அதிக வெப்பம்.",
        "hot": "வெப்பமான மதியம்: மையத்தைச் சுற்றி மிதமான வெப்ப அழுத்தம்; மதியம் 12 முதல் மாலை 4 மணி வரை அதிக வெப்பம்.",
        "normal": "வழக்கமான மதியம்: வெப்ப அழுத்தம் எதிர்பார்க்கப்படவில்லை.",
        "todo": "செய்ய வேண்டியவை:",
        "send": "இன்றிரவு: நமது மூத்தோருக்கு வெப்ப நினைவூட்டலை அனுப்பவும்.",
        "call_very_hot": "காலை 11 மணிக்கு முன்: தனியாக வசிக்கும் மூத்தோரை அழைக்கவும் அல்லது நேரில் சந்திக்கவும்; {focus} பகுதியிலிருந்து தொடங்கவும்.",
        "call_hot": "காலையில்: தனியாக வசிக்கும் மூத்தோரைத் தொலைபேசியில் அழைக்கவும்; {focus} பகுதியிலிருந்து தொடங்கவும்.",
        "indoors_very_hot": "மதியம் 12 – மாலை 4: வீட்டிற்குள் இருக்கவும், அடிக்கடி தண்ணீர் குடிக்கவும், வீடு மிகவும் சூடாக இருந்தால் {cool}-க்கு வரவும் நினைவூட்டவும்.",
        "indoors_hot": "மதியம் 12 – மாலை 4: வெளியே செல்வதைத் தவிர்க்கவும், தொடர்ந்து தண்ணீர் குடிக்கவும் நினைவூட்டவும்.",
        "routine": "வழக்கமான தொடர்பு மற்றும் சந்திப்புகள். கூடுதல் வெப்ப நடவடிக்கைகள் தேவையில்லை.",
        "haze": "காலையில்: இதயம் அல்லது நுரையீரல் பிரச்சினை உள்ள மூத்தோரிடம் மருந்துகள் உள்ளனவா எனச் சரிபார்த்து, ஜன்னல்களை மூடி வைக்க நினைவூட்டவும்.",
        "and": " மற்றும் ", "nearby": "அருகிலுள்ள பகுதிகள்",
        "foot": "இது HeatGuard முன்னறிவிப்பு. அன்றைய தினம் NEA-வின் சமீபத்திய அறிவுறுத்தல்களைப் பின்பற்றவும்.",
    },
}


class MessageError(ValueError):
    pass


def compose(*, level: str, day: dt.date, today: dt.date, language: str, audience: str, centre: str, cool: str | None,
            haze: bool = False, focus_areas: list[str] | None = None) -> str:
    """The message for one centre and day. `level` is the centre plan's level (very_hot / hot / normal)."""
    if language not in LANGUAGES:
        raise MessageError("Please choose English, 中文, Bahasa Melayu or தமிழ்.")
    if audience not in AUDIENCES:
        raise MessageError("Please choose who the message is for.")
    if level not in LEVELS:
        raise MessageError("Unknown heat level.")
    centre = (centre or "").strip() or {"en": "your centre", "zh": "您的中心", "ms": "pusat anda", "ta": "உங்கள் மையம்"}[language]
    cool = (cool or "").strip() or {"en": "the nearest Community Club", "zh": "最近的民众俱乐部", "ms": "Kelab Masyarakat yang terdekat",
                                    "ta": "அருகிலுள்ள சமூக மன்றம்"}[language]
    when = when_text(day, today, language)
    return (_seniors if audience == "seniors" else _staff)(language, level, when, centre, cool, haze, focus_areas or [])


def _seniors(lang, level, when, centre, cool, haze, _focus):
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


def _staff(lang, level, when, centre, cool, haze, focus):
    t = _STAFF[lang]
    names = [f.strip() for f in focus if f and f.strip()][:2]
    focus_text = t["and"].join(names) if names else t["nearby"]
    if level == "normal":
        todo = [t["routine"]]
    else:
        todo = [t["send"], t[f"call_{level}"].format(focus=focus_text), t[f"indoors_{level}"].format(cool=cool)]
    if haze:
        todo.append(t["haze"])
    lines = [t["head"].format(centre=centre, when=when), t[level], "", t["todo"]]
    lines += [f"{i}. {s}" for i, s in enumerate(todo, 1)]
    lines += ["", t["foot"]]
    return "\n".join(lines)
