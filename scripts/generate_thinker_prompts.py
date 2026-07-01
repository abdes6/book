import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import Thinker

BASE_STYLE = (
    "Style: warm beige background (#F7F3ED subtle warm cream), "
    "black baimiao (白描) line art, half-body portrait facing forward, "
    "single-color fine brushstrokes, minimalist traditional Chinese ink aesthetic, "
    "ample negative space, elegant hand-drawn line quality. "
    "No shading, no color except the warm beige background."
)

import re

ERA_ATTIRE = {
    "先秦": "ancient Chinese robes, crossed-collar garment (交领右衽), hair in a topknot or guan (冠)",
    "春秋": "ancient Chinese robes, crossed-collar garment (交领右衽), hair in a topknot or guan (冠)",
    "战国": "ancient Chinese robes, crossed-collar garment (交领右衽), loose sleeves, hair tied up",
    "古希腊": "ancient Greek himation or chiton draped over one shoulder, sandals, classical Greek attire",
    "德国": "18th-19th century German formal wear, frock coat, cravat or neckcloth",
    "奥地利": "19th century Central European formal attire, frock coat, vest",
    "瑞士": "19th century European formal wear, suit vest, collar",
    "英国": "19th century British formal attire, frock coat, cravat, Victorian style",
    "法国": "19th-20th century French formal wear, suit, coat, bohemian style for intellectuals",
    "近代": "19th century European formal attire, frock coat or suit, cravat",
}

SCHOOL_EXPRESSION = {
    "道家": "serene, detached expression, slight enigmatic smile, eyes half-closed in contemplation",
    "儒家": "warm, benevolent expression, gentle eyes, upright dignified posture",
    "古希腊哲学": "thoughtful, inquisitive expression, engaged and alert gaze",
    "唯心主义": "intense, contemplative gaze, furrowed brow in deep thought",
    "经验主义": "observant, analytical expression, calm focused eyes",
    "德国古典哲学": "serious, deeply contemplative expression, furrowed brow",
    "唯意志论": "intense, brooding expression, furrowed brow, penetrating gaze",
    "悲观主义": "melancholic, world-weary expression, deep-set eyes",
    "存在主义": "intense existential gaze, furrowed brow, piercing eyes",
    "生命哲学": "vibrant, passionate expression, intense eyes",
    "分析哲学": "sharp, analytical gaze, precise composed expression",
    "数理逻辑": "sharp focused eyes, precise expression",
    "精神分析": "intense, probing gaze, observant expression",
    "心理学": "analytical yet empathetic expression, attentive gaze",
    "个体心理学": "kind yet penetrating gaze, encouraging expression",
    "人本主义": "warm understanding expression, gentle eyes",
    "分析心理学": "wise, introspective gaze, deeply contemplative expression",
    "深度心理学": "deeply introspective, mysterious expression, probing eyes",
    "逻辑原子主义": "precise, analytical expression, clear focused eyes",
    "语言哲学": "intense analytical gaze, thoughtful expression",
    "现象学": "intensely reflective gaze, deeply thoughtful expression",
    "荒诞哲学": "ironic, knowing smile, defiant yet melancholic eyes",
    "启蒙运动": "enlightened, confident expression, clear determined eyes",
}

def match_era_key(era):
    for key in ERA_ATTIRE:
        if key in era:
            return ERA_ATTIRE[key]
    return "period-appropriate formal attire"

def match_school_expression(school):
    for key in SCHOOL_EXPRESSION:
        if key in school:
            return SCHOOL_EXPRESSION[key]
    return "thoughtful, contemplative expression"

def extract_visual_traits(bio, system_prompt, era, school):
    bio_lower = (bio or "").lower()
    prompt_lower = (system_prompt or "").lower()
    combined = bio_lower + " " + prompt_lower

    beard = ""
    if any(w in combined for w in ["胡", "髯", "beard", "大胡子", "长须"]):
        beard = "full beard"
    elif any(w in combined for w in ["山羊胡", "goatee", "胡须"]):
        beard = "goatee beard"
    elif any(w in combined for w in ["胡子", "mustache"]):
        beard = "prominent mustache"

    hair = ""
    if "光头" in combined or "bald" in combined:
        hair = "bald head"
    elif "卷发" in combined or "curly" in combined:
        hair = "curly hair"
    elif "white hair" in combined or "白发" in combined or "grey" in combined:
        hair = "white or grey hair"
    elif "long hair" in combined or "长发" in combined:
        hair = "long flowing hair"

    age_hint = ""
    if any(w in combined for w in ["老", "老年", "elderly", "aged", "白眉", "白髯"]):
        age_hint = "elderly, "
    elif any(w in combined for w in ["青年", "young"]):
        age_hint = "young, "

    expression = match_school_expression(school)

    parts = []
    if age_hint:
        parts.append(age_hint.strip(", "))
    if hair:
        parts.append(hair)
    if beard:
        parts.append(beard)

    return parts, expression


VISUAL_FEATURES = {
    "老子": "elderly man with long white eyebrows, long white beard, broad forehead, large earlobes, hair in a topknot bun (盘髻)",
    "孔子": "elderly man with flowing beard, kind eyes, broad forehead, hair tied in a bun, traditional scholar's cap (儒冠)",
    "苏格拉底": "bald head, broad flat nose, round face, thick beard, stocky build, snub nose, bulging eyes",
    "柏拉图": "high forehead, receding hair, full beard, aristocratic features, draped in himation",
    "亚里士多德": "balding crown, short hair and beard, refined features, thoughtful eyes, draped in Greek himation",
    "庄子": "free-spirited appearance, loose unkempt hair or casual topknot, thin face, long beard, Daoist robe, mischievous smile",
    "康德": "small frail build, large forehead, receding hair pulled back, small wig, bright piercing eyes, 18th century formal coat",
    "黑格尔": "receding hairline, sideburns, stern expression, high forehead, glasses or spectacles, 19th century frock coat",
    "叔本华": "bushy white side-whiskers, receding hair, penetrating blue eyes, round face, 19th century suit, bitter expression",
    "尼采": "enormous drooping walrus mustache, receding hairline, deep-set intense eyes, high forehead, prominent nose, 19th century suit",
    "弗雷格": "large bushy beard covering most of face, receding hair, spectacles, serious expression, 19th century formal wear",
    "弗洛伊德": "neatly trimmed beard, receding hair, cigar, piercing dark eyes, round face, vest and suit, intelligent gaze",
    "阿德勒": "neatly trimmed mustache, receding hair, round wire-rimmed glasses, kind yet penetrating eyes, 20th century suit",
    "荣格": "broad face, high forehead, receding hair, intense deep-set eyes, thoughtful expression, suit vest, pipe occasionally",
    "罗素": "bushy eyebrows, sharp penetrating eyes, receding hair, tall lean figure, 20th century suit, alert intellectual expression",
    "维特根斯坦": "sharp angular features, intense deep-set eyes, receding hair, thin lips, austere expression, simple suit",
    "萨特": "cross-eyed gaze (strabismus), receding hair, mustache, pipe, intense intellectual expression, 20th century French intellectual attire, turtleneck or suit",
    "加缪": "handsome features, cigarette often in mouth, wavy hair, overcoat collar turned up, intense thoughtful expression, French bohemian style",
}

def build_prompt_for_thinker(thinker):
    name_en = {
        "老子": "Laozi (Li Er)",
        "孔子": "Confucius (Kong Qiu)",
        "苏格拉底": "Socrates",
        "柏拉图": "Plato",
        "亚里士多德": "Aristotle",
        "庄子": "Zhuangzi (Chuang Tzu)",
        "康德": "Immanuel Kant",
        "黑格尔": "Georg Wilhelm Friedrich Hegel",
        "叔本华": "Arthur Schopenhauer",
        "尼采": "Friedrich Nietzsche",
        "弗雷格": "Gottlob Frege",
        "弗洛伊德": "Sigmund Freud",
        "阿德勒": "Alfred Adler",
        "荣格": "Carl Gustav Jung",
        "罗素": "Bertrand Russell",
        "维特根斯坦": "Ludwig Wittgenstein",
        "萨特": "Jean-Paul Sartre",
        "加缪": "Albert Camus",
    }.get(thinker.name, thinker.name)

    attire = match_era_key(thinker.era)
    traits, expression = extract_visual_traits(thinker.bio, thinker.system_prompt, thinker.era, thinker.school)
    visual_features = VISUAL_FEATURES.get(thinker.name, "")

    # Build visual description
    desc_parts = [f"Half-body portrait of {name_en}."]
    if visual_features:
        desc_parts.append(f"Appearance: {visual_features}.")
    if traits:
        desc_parts.append(" ".join(traits).capitalize() + ".")
    desc_parts.append(f"Wearing {attire}.")
    desc_parts.append(f"Expression: {expression}.")

    # Name label in Chinese
    desc_parts.append(f"Clear recognizable likeness of {thinker.name}.")

    visual_desc = " ".join(desc_parts)
    return f"{visual_desc}\n\n{BASE_STYLE}"


def generate_single(slug):
    app = create_app()
    with app.app_context():
        t = Thinker.query.filter_by(slug=slug).first()
        if not t:
            print(f"Thinker {slug} not found")
            return
        prompt = build_prompt_for_thinker(t)
        print("=" * 60)
        print(f"Prompt for {t.name} ({t.slug}):")
        print("=" * 60)
        print(prompt)
        print()
        return prompt


def generate_batch():
    app = create_app()
    with app.app_context():
        thinkers = Thinker.query.order_by(Thinker.sort_order).all()
        tasks = []
        for t in thinkers:
            prompt = build_prompt_for_thinker(t)
            tasks.append({
                "id": t.slug,
                "prompt": prompt,
                "image": f"app/static/images/thinkers/{t.slug}.png",
                "provider": "seedream",
                "ar": "4:5",
                "quality": "2k"
            })
            print(f"[{t.slug}] prompt generated")

        batch = {"jobs": 4, "tasks": tasks}
        out_path = os.path.join(os.path.dirname(__file__), "thinker_batch.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
        print(f"\nBatch file saved: {out_path} ({len(tasks)} tasks)")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        generate_single(sys.argv[1])
    else:
        generate_batch()
