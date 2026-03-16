const chat = document.getElementById("chat");
const input = document.getElementById("input");
const sendBtn = document.getElementById("send");

// -- User Identity --
let userId = localStorage.getItem("sabi_user_id");
if (!userId) {
  userId = "user_" + Math.random().toString(36).substr(2, 9);
  localStorage.setItem("sabi_user_id", userId);
}

// -- State Management (Profile) --
let userState = JSON.parse(localStorage.getItem("sabi_state") || '{"anxiety": 0, "stress": 0, "mood": 5}');

const anxietySlider = document.getElementById("slider-anxiety");
const anxietyVal = document.getElementById("anxiety-val");
const stressSlider = document.getElementById("slider-stress");
const stressVal = document.getElementById("stress-val");
const moodSlider = document.getElementById("slider-mood");
const moodVal = document.getElementById("mood-val");

function saveState() {
  userState.anxiety = parseInt(anxietySlider.value);
  userState.stress = parseInt(stressSlider.value);
  userState.mood = parseInt(moodSlider.value);
  localStorage.setItem("sabi_state", JSON.stringify(userState));
  syncSliders();
}

function syncSliders() {
  if (!anxietySlider) return;
  anxietySlider.value = userState.anxiety;
  anxietyVal.textContent = userState.anxiety;
  stressSlider.value = userState.stress;
  stressVal.textContent = userState.stress;
  moodSlider.value = userState.mood;
  moodVal.textContent = userState.mood;
}

if (anxietySlider) {
  [anxietySlider, stressSlider, moodSlider].forEach(s => s.addEventListener("input", saveState));
  syncSliders();
}


// -- Chat History --
async function loadChatHistory() {
  chat.innerHTML = "";
  try {
    const res = await fetch(`/api/history?user_id=${userId}`);
    const history = await res.json();
    
    if (history.length === 0) {
      addMessageUI("Привет. Я Саби. Я не врач и не замена терапии, но могу поддержать и помочь разобраться.\nНапиши, что сейчас происходит.", "sabi");
    } else {
      history.forEach(msg => addMessageUI(msg.text, msg.role));
    }
  } catch (e) {
    addMessageUI("Ошибка загрузки истории.", "sabi");
  }
}

function addMessageUI(text, who) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${who}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
}

loadChatHistory();


// -- Networking --
function showTyping() {
  const wrap = document.createElement("div");
  wrap.className = "msg sabi typing-wrap";
  const bubble = document.createElement("div");
  bubble.className = "bubble typing-indicator";
  bubble.innerHTML = '<div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>';
  wrap.appendChild(bubble);
  chat.appendChild(wrap);
  chat.scrollTop = chat.scrollHeight;
  return wrap;
}

function hideTyping(wrap) {
  if (wrap && wrap.parentNode) {
    wrap.parentNode.removeChild(wrap);
  }
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;

  addMessageUI(text, "user");
  input.value = "";
  input.style.height = "auto";
  input.focus();

  const typingIndicator = showTyping();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({
        message: text,
        state: userState,
        user_id: userId
      })
    });

    const data = await res.json();
    hideTyping(typingIndicator);
    addMessageUI(data.reply || "…", "sabi");
  } catch (e) {
    hideTyping(typingIndicator);
    addMessageUI("Ошибка связи с сервером. Проверь, запущен ли backend.", "sabi");
  }
}

sendBtn.addEventListener("click", sendMessage);

input.addEventListener("input", function() {
  this.style.height = "auto";
  this.style.height = (this.scrollHeight) + "px";
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});


// -- Dynamics --
async function loadDynamics() {
  const container = document.getElementById("dynamics-list");
  if (!container) return;
  
  try {
    const res = await fetch(`/api/dynamics?user_id=${userId}`);
    const arr = await res.json();
    
    if (arr.length === 0) {
      container.innerHTML = `<div class="placeholder">Пока нет данных. Отправь сообщение в чат с выставленным состоянием!</div>`;
      return;
    }
    
    container.innerHTML = "";
    arr.forEach(item => {
      const d = new Date(item.created_at);
      
      // Convert UTC 'created_at' from SQLite to local date string easily by appending 'Z' if missing
      const dateObj = new Date(item.created_at + (item.created_at.includes('Z') ? '' : 'Z'));
      
      let timeStr = dateObj.toLocaleDateString() + ' ' + dateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
      if (isNaN(dateObj.getTime())) {
          timeStr = item.created_at; // fallback to string if parsing fails
      }

      const el = document.createElement("div");
      el.className = "dynamic-item";
      
      const makeBar = (label, val, max, type) => {
        const w = (val / max) * 100;
        return `
          <div class="dynamic-row">
            <div class="dynamic-label">${label}</div>
            <div class="dynamic-bar-bg">
              <div class="dynamic-bar-fill ${type}" style="width: ${w}%"></div>
            </div>
            <div class="dynamic-val">${val}</div>
          </div>
        `;
      };

      el.innerHTML = `
        <div class="dynamic-time">${timeStr}</div>
        ${makeBar('Тревога', item.anxiety, 10, item.anxiety >= 7 ? 'high' : item.anxiety >= 4 ? 'mid' : 'good')}
        ${makeBar('Стресс', item.stress, 10, item.stress >= 7 ? 'high' : item.stress >= 4 ? 'mid' : 'good')}
        ${makeBar('Настроение', item.mood, 10, item.mood <= 3 ? 'high' : item.mood <= 6 ? 'mid' : 'good')}
      `;
      container.appendChild(el);
    });
  } catch(e) {
    container.innerHTML = `<div class="placeholder">Ошибка загрузки...</div>`;
  }
}

// -- Tabs --
const tabs = document.querySelectorAll(".tab");
const views = document.querySelectorAll(".view");

tabs.forEach(tab => {
  tab.addEventListener("click", () => {
    if (tab.disabled) return;
    tabs.forEach(t => t.classList.remove("active"));
    views.forEach(v => v.classList.remove("active"));
    
    tab.classList.add("active");
    const viewId = "view-" + tab.dataset.view;
    document.getElementById(viewId).classList.add("active");
    
    if (viewId === "view-dynamics") {
      loadDynamics();
    }
  });
});


// -- Exercises Library --
async function loadExercises() {
  const container = document.getElementById("exercises-list");
  if (!container) return;
  
  try {
    const res = await fetch("/api/exercises");
    const arr = await res.json();
    container.innerHTML = "";
    
    arr.forEach(ex => {
      const el = document.createElement("div");
      el.className = "exercise-card";
      const durationMins = Math.ceil(ex.duration_sec / 60);
      
      const stepsHtml = ex.steps.map(s => `<li>${s}</li>`).join("");
      
      el.innerHTML = `
        <h3>${ex.title}</h3>
        <span class="exercise-type">${ex.type} • ${durationMins} мин</span>
        <ol class="exercise-steps">
          ${stepsHtml}
        </ol>
      `;
      container.appendChild(el);
    });
  } catch(e) {
    container.innerHTML = `<div class="placeholder">Ошибка загрузки библиотеки... (${e.message})</div>`;
  }
}

loadExercises();
