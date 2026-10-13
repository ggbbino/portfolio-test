// Портфолио: сцена подъёма телефона (CSS scroll-driven), демо записи, вкладки, подсветка разделов.
// Без библиотек. При «меньше движения» или без поддержки сцена стоит на месте, блоки сразу видны.
const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------- Общий кадр прокрутки ----------
// Одно событие прокрутки → не больше одного кадра (requestAnimationFrame).
// В кадре читается только window.scrollY; положения разделов замеряются
// заранее (при загрузке и изменении размеров), поэтому во время прокрутки
// нет чтения раскладки и принудительных пересчётов.
// Высота экрана на телефоне фиксируется: панель Safari, которая прячется
// и появляется при прокрутке, не сдвигает сцену. Пересчёт — при смене ширины
// (поворот телефона), на компьютере — при любом изменении окна.
const page = (function frameLoop() {
  const coarse = window.matchMedia("(pointer: coarse)").matches;
  const view = { w: window.innerWidth, h: window.innerHeight };
  const measures = [], jobs = [];
  let queued = false;
  function run() {
    queued = false;
    const y = window.scrollY;
    jobs.forEach((job) => job(y));
  }
  const request = () => { if (!queued) { queued = true; requestAnimationFrame(run); } };
  function remeasure() {
    if (!coarse || window.innerWidth !== view.w) { view.w = window.innerWidth; view.h = window.innerHeight; }
    measures.forEach((m) => m());
    request();
  }
  // Положение элемента от начала страницы (без учёта прокрутки)
  const docTop = (el) => el.getBoundingClientRect().top + window.scrollY;

  window.addEventListener("scroll", request, { passive: true });
  let resizeQueued = false;
  window.addEventListener("resize", () => {
    if (resizeQueued) return;
    resizeQueued = true;
    requestAnimationFrame(() => { resizeQueued = false; remeasure(); });
  });
  window.addEventListener("pageshow", remeasure);           // возврат «назад» в Safari
  document.addEventListener("visibilitychange", () => { if (!document.hidden) request(); });
  window.addEventListener("load", remeasure);               // картинки и шрифты могли сдвинуть разделы
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(remeasure);
  if (window.ResizeObserver) new ResizeObserver(remeasure).observe(document.body);

  return {
    view, docTop, request,
    add(measure, job) { measures.push(measure); jobs.push(job); measure(); job(window.scrollY); },
  };
})();

// ---------- Появление блоков: контент никогда не остаётся скрытым ----------
// Прячем только то, что на старте ниже экрана, и показываем заранее —
// за 20% высоты экрана. Блоки, пришедшие одной группой, появляются
// по очереди с небольшой задержкой. После появления служебный класс
// снимается, чтобы долгий переход не мешал нажатиям.
// Страховка: раз в секунду показываем блоки ближе 1,2 экрана (если
// наблюдатель их пропустил). Когда показано всё — таймер снимается.
(function reveal() {
  if (calm) return;
  const show = (el, delay) => {
    el.style.transitionDelay = delay ? `${delay}ms` : "";
    el.classList.add("is-in");
    el.classList.remove("will-reveal");
  };
  let pending = [...document.querySelectorAll("[data-reveal]")]
    .filter((el) => el.getBoundingClientRect().top > window.innerHeight);
  if (!pending.length) return;
  pending.forEach((el) => el.classList.add("will-reveal"));

  document.addEventListener("transitionend", (e) => {
    const el = e.target;
    if (e.propertyName === "transform" && el.classList.contains("is-in")) {
      el.classList.remove("is-in");
      el.style.transitionDelay = "";
    }
  });

  const io = new IntersectionObserver((entries) => {
    entries
      .filter((e) => e.isIntersecting)
      .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
      .forEach((e, i) => { show(e.target, Math.min(i, 3) * 90); io.unobserve(e.target); });
  }, { rootMargin: "0px 0px 20% 0px" });
  pending.forEach((el) => io.observe(el));

  function sweep() {
    pending = pending.filter((el) => el.classList.contains("will-reveal"));
    // Сначала читаем все положения, потом меняем классы — без пересчёта на каждом шаге
    const limit = window.innerHeight * 1.2;
    const due = pending.filter((el) => el.getBoundingClientRect().top < limit);
    due.forEach((el) => { show(el, 0); io.unobserve(el); });
    pending = pending.filter((el) => !due.includes(el));
    if (!pending.length) { clearInterval(timer); window.removeEventListener("pageshow", sweep); io.disconnect(); }
  }
  window.addEventListener("pageshow", sweep);
  const timer = setInterval(sweep, 1000); // если кадры не рисуются (вкладка в фоне, слабый телефон)
})();

// ---------- Led_Box: переключатель или нажатие выводит экран вперёд ----------
(function pair() {
  const box = document.getElementById("pair");
  const cap = document.getElementById("pairCap");
  if (!box || !cap) return;
  const buttons = [...document.querySelectorAll(".switch button")];
  const text = {
    client: "Клиент выбирает услугу, день и&nbsp;время.",
    master: "Мастер видит все записи на&nbsp;день, отметки и&nbsp;сумму.",
  };
  function show(who) {
    box.dataset.front = who;
    cap.innerHTML = text[who];
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.show === who)));
  }
  buttons.forEach((b) => b.addEventListener("click", () => show(b.dataset.show)));
  box.querySelectorAll(".pair__hit").forEach((hit) => {
    hit.addEventListener("click", () => show(hit.closest("[data-shot]").dataset.shot));
  });
})();

// ---------- Plates: вкладки с клавиатурой (стрелки, Home, End) ----------
(function plates() {
  const screen = document.getElementById("platesScreen");
  const cap = document.getElementById("platesCap");
  const tabs = [...document.querySelectorAll('.plates__tabs [role="tab"]')];
  if (!screen || !cap || !tabs.length) return;
  const imgs = [...screen.querySelectorAll("img")];
  const text = [
    "План на&nbsp;сегодня. Вес подставляется из&nbsp;прошлого раза, после подхода запускается таймер отдыха.",
    "Ближайшие тренировки по&nbsp;очереди — верх, низ — и&nbsp;упражнения с&nbsp;подходами и&nbsp;отдыхом.",
    "График веса тела с&nbsp;целью и&nbsp;история каждого упражнения.",
  ];
  function select(i, focus) {
    screen.dataset.active = i;
    screen.setAttribute("aria-labelledby", tabs[i].id);
    cap.innerHTML = text[i];
    tabs.forEach((t, n) => {
      t.setAttribute("aria-selected", String(n === i));
      t.tabIndex = n === i ? 0 : -1; // Tab попадает только на выбранную вкладку
    });
    imgs.forEach((img, n) => img.setAttribute("aria-hidden", String(n !== i)));
    if (focus) tabs[i].focus();
  }
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => select(i, false));
    t.addEventListener("keydown", (e) => {
      const next = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
      if (next === undefined) return;
      e.preventDefault();
      select((next + tabs.length) % tabs.length, true);
    });
  });
})();

// ---------- Как я работаю: этап в середине экрана подсвечивается ----------
(function flow() {
  const steps = document.querySelectorAll(".flow__step");
  if (!steps.length) return;
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => e.target.classList.toggle("is-now", e.isIntersecting));
  }, { rootMargin: "-45% 0px -45% 0px" }); // узкая полоса посередине экрана
  steps.forEach((s) => io.observe(s));
})();

// ---------- Шапка: текущий раздел в меню, плотный фон над оранжевым финалом ----------
(function bar() {
  const bar = document.querySelector(".bar");
  if (!bar) return;
  const fin = document.querySelector(".final");
  const links = [...bar.querySelectorAll(".bar__nav a")].map((a) => ({
    a, here: null, ranges: [],
    sections: a.dataset.for.split(" ").map((id) => document.getElementById(id)).filter(Boolean),
  }));
  let barH = 0, finTop = Infinity, onSignal = null;
  function measure() {
    barH = bar.offsetHeight;
    finTop = fin ? page.docTop(fin) : Infinity;
    links.forEach((l) => { l.ranges = l.sections.map((s) => { const t = page.docTop(s); return [t, t + s.offsetHeight]; }); });
  }
  function update(y) {
    const signal = finTop - y <= barH;
    if (signal !== onSignal) { onSignal = signal; bar.classList.toggle("on-signal", signal); }
    const line = y + page.view.h / 3; // раздел, который пересекает линию на трети экрана
    links.forEach((l) => {
      const here = l.ranges.some(([top, bottom]) => top <= line && bottom > line);
      if (here === l.here) return;
      l.here = here;
      l.a.classList.toggle("is-here", here);
      if (here) l.a.setAttribute("aria-current", "true"); else l.a.removeAttribute("aria-current");
    });
  }
  page.add(measure, update);
})();

// ---------- Сцена: подъём телефона при прокрутке ----------
// Само движение — нативная CSS-анимация от прокрутки (style.css, «Сцена подъёма
// телефона»): браузер ведёт её сам, скрипт не пишет transform ни в одном кадре.
// Здесь только одно: узнать, что телефон встал на место, и запустить демо.
// Признак — центр рамки .crop поднялся выше 54% высоты экрана (≈97% пути
// анимации). Для этого в центр рамки ставится невидимая точка, и за ней следит
// IntersectionObserver — без обработчика прокрутки и без вычислений в кадре.
// После запуска демо наблюдатель отключается.
// Без поддержки animation-timeline и при «меньше движения» телефон стоит на месте
// с самого начала — демо готово сразу (стартует, когда его видно).
const scene = (function sceneDone() {
  const hero = document.querySelector("[data-scene]");
  const frame = hero && hero.querySelector(".crop");
  let locked = false;
  const waiting = [];
  const api = { whenLocked: () => new Promise((r) => (locked ? r() : waiting.push(r))) };
  function lock() {
    if (locked) return;
    locked = true;
    waiting.splice(0).forEach((r) => r());
  }
  const native = window.CSS && CSS.supports("animation-timeline: view()");
  if (!hero || !frame || calm || !native) { lock(); return api; }

  const dot = document.createElement("span");
  dot.setAttribute("aria-hidden", "true");
  dot.style.cssText = "position:absolute;left:0;top:50%;width:1px;height:1px;pointer-events:none";
  frame.appendChild(dot);
  // Зона наблюдения — верхние 54% экрана. Точка внутри или уже выше — сцена закончилась.
  const io = new IntersectionObserver(([e]) => {
    const rootBottom = e.rootBounds ? e.rootBounds.bottom : window.innerHeight * .54;
    if (e.isIntersecting || e.boundingClientRect.top < rootBottom) { io.disconnect(); lock(); }
  }, { rootMargin: "0px 0px -46% 0px" });
  io.observe(dot);
  return api;
})();

// ---------- Демо записи ----------
// Один бесконечный сценарий. Время идёт, только когда демо видно и вкладка открыта;
// иначе сценарий спит без таймеров и просыпается при возвращении.
(function demo() {
  const screen = document.getElementById("demo");
  const box = document.getElementById("demoBox");
  if (!screen || !box) return;
  const $ = (s) => screen.querySelector(s);
  const client = $('[data-scr="client"]'), master = $('[data-scr="master"]');
  const finger = $(".finger"), toast = $(".toast"), done = $(".done");
  const go = $('[data-t="go"]'), newSlot = $(".slot--new");
  const cap = document.getElementById("demoCap");
  const stepEls = [...box.querySelectorAll(".steps li")];

  let onScreen = false, wake = null;
  const running = () => onScreen && !document.hidden;
  const nudge = () => { if (wake && running()) { const w = wake; wake = null; w(); } };
  new IntersectionObserver(([e]) => { onScreen = e.isIntersecting; nudge(); }, { threshold: 0.2 }).observe(box);
  document.addEventListener("visibilitychange", nudge);
  window.addEventListener("pageshow", nudge);

  // Пауза, которая «замирает», пока демо не видно
  async function wait(ms) {
    let left = ms;
    while (left > 0) {
      if (!running()) await new Promise((r) => { wake = r; });
      const start = performance.now();
      await new Promise((r) => setTimeout(r, Math.min(left, 200)));
      if (running()) left -= performance.now() - start;
    }
  }

  const captions = [
    "Клиент открывает страницу записи мастера.",
    "Клиент выбирает услугу — ремонт скола.",
    "Выбирает день и свободное время.",
    "Нажимает «Записаться» — запись готова без звонка.",
    "Мастер сразу видит нового клиента в расписании.",
  ];
  function setStep(n) {
    stepEls.forEach((li, i) => {
      li.classList.toggle("is-done", i + 1 < n);
      li.classList.toggle("is-now", i + 1 === n);
    });
    cap.textContent = captions[n];
  }

  // Положение кнопки по раскладке (offsetLeft/Top), а не по экранным координатам:
  // наклон и масштаб телефона во время сцены не сбивают «палец».
  function spot(el, dx = 0, dy = 0) {
    let x = el.offsetWidth / 2, y = el.offsetHeight / 2;
    for (let n = el; n && n !== screen; n = n.offsetParent) { x += n.offsetLeft; y += n.offsetTop; }
    return `translate(${x + dx}px, ${y + dy}px)`;
  }
  function jump(t) {
    finger.classList.add("no-move");
    finger.style.transform = t;
    void finger.offsetWidth;
    finger.classList.remove("no-move");
  }
  async function tap(el) {
    finger.style.transform = spot(el);
    await wait(900);
    finger.classList.remove("is-tap"); void finger.offsetWidth; finger.classList.add("is-tap");
    el.classList.add("is-tap");
    await wait(180);
    el.classList.remove("is-tap");
  }
  function reset() {
    screen.querySelectorAll(".is-on").forEach((el) => el.classList.remove("is-on"));
    go.classList.remove("is-ready");
    master.classList.remove("is-active");
    client.classList.remove("is-left");
    client.classList.add("is-active");
    setStep(0);
  }

  async function loop() {
    if (document.fonts && document.fonts.ready) await document.fonts.ready;
    await scene.whenLocked(); // демо стартует, когда телефон встал на место
    for (;;) {
      reset();
      await wait(600);
      const svc = $('[data-t="svc"]');
      jump(spot(svc, 30, 50));
      finger.classList.add("is-on");
      setStep(1);
      await wait(450);
      await tap(svc); svc.classList.add("is-on");
      await wait(350);
      setStep(2);
      for (const key of ["day", "time"]) {
        const el = $(`[data-t="${key}"]`);
        await tap(el); el.classList.add("is-on");
        await wait(350);
      }
      setStep(3);
      go.classList.add("is-ready");
      await tap(go);
      finger.classList.remove("is-on");
      done.classList.add("is-on");
      await wait(1700);

      setStep(4);
      client.classList.remove("is-active");
      client.classList.add("is-left");
      master.classList.add("is-active");
      await wait(600);
      toast.classList.add("is-on");
      await wait(700);
      newSlot.classList.add("is-on");
      await wait(2400);
      toast.classList.remove("is-on");
      await wait(1800);
    }
  }
  loop();
})();
