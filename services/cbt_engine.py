from __future__ import annotations
from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import os

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

CRISIS_MARKERS = [
    "не хочу жить", "хочу умереть", "покончить", "суицид", "самоубий",
    "причиню себе вред", "самоповреж", "порез", "повеш", "таблет", "умру"
]


@dataclass
class Reply:
    text: str
    intent: str  # normal | crisis
    next_action: Optional[str] = None
    suggested_exercise_id: Optional[str] = None


def is_crisis(text: str) -> bool:
    t = (text or "").lower()
    return any(m in t for m in CRISIS_MARKERS)


def infer_topic(text: str) -> str:
    """Очень простой MVP-классификатор темы по ключевым словам."""
    t = (text or "").lower()
    if any(w in t for w in ["тревог", "страш", "паник", "переживаю", "волн"]):
        return "anxiety"
    if any(w in t for w in ["гру", "пуст", "нет сил", "депрес", "безнад"]):
        return "low_mood"
    if any(w in t for w in ["злю", "раздраж", "бесит", "ярост"]):
        return "anger"
    if any(w in t for w in ["отношен", "ревност", "границ", "ссора", "семь", "родител"]):
        return "relationships"
    if any(w in t for w in ["экзам", "учеб", "вуз", "сесс", "работ", "дедлайн"]):
        return "stress"
    return "general"


def load_exercises(data_path: Path) -> List[Dict[str, Any]]:
    return json.loads(data_path.read_text(encoding="utf-8"))


def pick_exercise(state: Dict[str, Any], topic: str, exercises: List[Dict[str, Any]]) -> str:
    """
    MVP-выбор упражнения:
    - если тревога/стресс высокий -> stabilization
    - иначе -> CBT/skills
    """
    anxiety = int(state.get("anxiety", 0) or 0)
    stress = int(state.get("stress", 0) or 0)

    if max(anxiety, stress) >= 7:
        preferred = ["stabilization"]
    elif max(anxiety, stress) >= 4:
        preferred = ["cbt", "stabilization"]
    else:
        preferred = ["skills", "planning", "communication", "cbt"]

    for p in preferred:
        for ex in exercises:
            if ex.get("type") == p:
                return ex["id"]

    return exercises[0]["id"]


def format_exercise(ex: Dict[str, Any]) -> str:
    steps = "\n".join([f"— {s}" for s in ex.get("steps", [])])
    mins = max(1, int(round(ex.get("duration_sec", 60) / 60)))
    return f"Упражнение: {ex.get('title')} (≈ {mins} мин)\n{steps}"


def cbt_reply(user_text: str, state: Dict[str, Any], exercises: List[Dict[str, Any]], history: Optional[List[Dict[str, Any]]] = None) -> Reply:
    """КПТ-движок: поддержка → вопрос → инструмент (с поддержкой AI)."""
    user_text = (user_text or "").strip()
    state = state or {}
    history_list = history or []

    # Crisis mode (soft protocol)
    if is_crisis(user_text):
        text = (
            "Мне очень важно, чтобы ты сейчас был(а) в безопасности. Я здесь и слышу тебя.\n\n"
            "Пожалуйста, свяжись прямо сейчас с кем-то, кто может помочь:\n\n"
            "🇷🇺 Россия — телефон доверия: 8-800-2000-122 (бесплатно, круглосуточно)\n"
            "🇰🇿 Казахстан: 150 (экстренная психологическая помощь)\n"
            "🇺🇦 Украина: 7333 (бесплатно)\n"
            "🇧🇾 Беларусь: 8-017-290-44-44\n\n"
            "Если ты в непосредственной опасности — позвони в скорую (103) или попроси кого-то рядом побыть с тобой.\n\n"
            "Я здесь, если хочешь написать — но живые люди сейчас важнее."
        )
        return Reply(text=text, intent="crisis", next_action="safety_check")

    topic = infer_topic(user_text)

    # Support (moderately soft)
    support_map = {
        "anxiety": "Похоже, тревога сейчас довольно сильная. Это тяжело, но с этим можно работать шаг за шагом.",
        "low_mood": "Похоже, сейчас много тяжести и мало ресурса. Давай аккуратно разберём, что происходит.",
        "anger": "Похоже, внутри много напряжения и злости. Это сигнал, что что-то важно для тебя.",
        "relationships": "Похоже, ситуация в отношениях задевает тебя. Давай посмотрим, что именно болит.",
        "stress": "Похоже, нагрузка давит. Давай снизим остроту и выберем следующий шаг.",
        "general": "Похоже, тебе сейчас непросто. Я рядом — давай разберёмся спокойно."
    }
    support = support_map.get(topic, support_map["general"])

    # One clarifying CBT question
    question = "Что случилось прямо перед тем, как стало так? Опиши фактами в 1–2 предложениях."

    # Tool: pick exercise
    ex_id = pick_exercise(state, topic, exercises)
    ex = next(e for e in exercises if e["id"] == ex_id)
    tool = format_exercise(ex)

    # ------------------ AI ENGINE (Если есть ключ и установлен openai) ------------------
    api_key = os.getenv("OPENAI_API_KEY")
    if HAS_OPENAI and api_key:
        try:
            client = openai.OpenAI(api_key=api_key)
            messages = [
                {"role": "system", "content": (
                    "Ты Саби — эмпатичный AI-ассистент, основанный на когнитивно-поведенческой терапии (КПТ). "
                    "Твоя задача — оказать бережную поддержку пользователю, валидировать его чувства и предложить технику для работы с состоянием. "
                    "ПРАВИЛА:\n1. Никаких медицинских диагнозов или советов по препаратам.\n2. Избегай 'токсичного позитива'.\n3. Пиши лаконично (до 4 абзацев).\n"
                    f"Тема: {topic}.\n"
                    f"Состояние по 0-10: Тревога {state.get('anxiety', 0)}, Стресс {state.get('stress', 0)}, Настроение {state.get('mood', 5)}.\n\n"
                    f"ОБЯЗАТЕЛЬНО предложи пользователю выполнить эту технику:\n{tool}"
                )}
            ]
            
            # Добавляем историю сессии (max 6 сообщений)
            recent_history = history_list[-6:] if len(history_list) > 6 else history_list
            for msg in recent_history:
                role = "assistant" if msg.get("role") == "sabi" else "user"
                messages.append({"role": role, "content": msg.get("text", "")})
                
            messages.append({"role": "user", "content": user_text})
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=400
            )
            ai_text = str(response.choices[0].message.content)
            return Reply(text=ai_text, intent="ai_normal", next_action="ai_mode", suggested_exercise_id=ex_id)
        except Exception as e:
            print(f"OpenAI error (falling back to strict rules): {e}")
    # ------------------------------------------------------------------------------------

    # Ask micro-scale (to build future dynamics)
    ask_scale = "И ещё: оцени сейчас тревогу и стресс по шкале 0–10 (если можешь)."

    text = f"{support}\n\n{question}\n\n{tool}\n\n{ask_scale}"
    return Reply(text=text, intent="normal", next_action="micro_scale", suggested_exercise_id=ex_id)
