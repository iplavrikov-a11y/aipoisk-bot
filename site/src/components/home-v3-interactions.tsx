"use client";

import { useEffect } from "react";

type StepOptions = {
  force?: boolean;
  focus?: boolean;
  fromAuto?: boolean;
  initial?: boolean;
  history?: "push" | "replace";
  updateUrl?: boolean;
};

/**
 * Progressive enhancement for the server-rendered Home v3 markup.
 * No content depends on this component: without JS the page and first step stay visible.
 */
export function HomeV3Interactions() {
  useEffect(() => {
    const scope = document.querySelector<HTMLElement>(".home-v3");
    if (!scope) return;

    const ac = new AbortController();
    const reduceQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const reduceMotion = () => reduceQuery.matches;
    const $ = <T extends HTMLElement = HTMLElement>(selector: string, root: ParentNode = scope) =>
      root.querySelector<T>(selector);
    const $$ = <T extends HTMLElement = HTMLElement>(selector: string, root: ParentNode = scope) =>
      Array.from(root.querySelectorAll<T>(selector));

    let revealObserver: IntersectionObserver | undefined;
    let revealFallback = 0;
  /* -------------------------------------------------------
     Scroll reveal
     ------------------------------------------------------- */

  const revealItems = $$("[data-reveal]");
  if (revealItems.length) {
    if (reduceMotion() || !("IntersectionObserver" in window)) {
      revealItems.forEach((item) => item.classList.add("is-in"));
    } else {
      const revealObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-in");
          revealObserver.unobserve(entry.target);
        });
      }, { threshold: 0.14, rootMargin: "0px 0px -7% 0px" });
      revealItems.forEach((item) => revealObserver.observe(item));
      // Keep content visible if the revealObserver never fires (e.g. unusual viewport).
      revealFallback = window.setTimeout(() => {
        revealItems.forEach((item) => {
          const rect = item.getBoundingClientRect();
          if (rect.top < window.innerHeight * 0.92) item.classList.add("is-in");
        });
      }, 900);
    }
  }

  /* -------------------------------------------------------
     Interactive five-step walkthrough
     ------------------------------------------------------- */

  const shell = $(".demo-shell");
  const tabs = $$("[data-step]");
  const views = $$("[data-step-view]");
  const progressBars = $$(".stage-progress i");
  const stepCurrent = $("[data-step-current]");
  const stepTitle = $("[data-step-title]");
  const stepOutput = $("[data-step-output]");
  const prevButton = $<HTMLButtonElement>("[data-step-prev]");
  const nextButton = $<HTMLButtonElement>("[data-step-next]");
  const executeButton = $<HTMLButtonElement>("[data-step-execute]");
  const playButton = $<HTMLButtonElement>("[data-demo-play]");
  const playLabel = $("[data-demo-play-label]");
  const playIcon = playButton ? $(".demo-play__icon", playButton) : null;

  const stepData: Record<number, { title: string; output: string }> = {
    1: { title: "Спецификация", output: "структурированная спецификация, а не пересказ документа" },
    2: { title: "Разбор", output: "поля с фрагментами-источниками; пустые поля не додумываются" },
    3: { title: "Поставщики", output: "список кандидатов и вопросы, которые нужно уточнить" },
    4: { title: "Аналоги", output: "таблица отличий, где видно, что требует проверки" },
    5: { title: "Запрос КП", output: "черновик письма с позициями и вопросами по поставке" }
  };

  const state: { step: number; visited: Set<number>; autoplay: boolean; timer: number } = {
    step: 1,
    visited: new Set([1]),
    autoplay: false,
    timer: 0
  };

  function paused(): boolean {
    return reduceMotion();
  }

  function clearAuto(): void {
    if (state.timer) {
      window.clearTimeout(state.timer);
      state.timer = 0;
    }
  }

  function scheduleAuto(): void {
    clearAuto();
    if (!state.autoplay || paused()) return;
    state.timer = window.setTimeout(() => {
      if (!state.autoplay) return;
      if (state.step >= 5) {
        stopAutoplay();
        return;
      }
      setStep(state.step + 1, { fromAuto: true });
    }, 7500);
  }

  function updatePlayUI(): void {
    if (!playButton) return;
    playButton.classList.toggle("is-playing", state.autoplay);
    playButton.setAttribute("aria-pressed", String(state.autoplay));
    if (playLabel) playLabel.textContent = state.autoplay ? "Пауза" : (state.step === 5 ? "Повторить" : "Смотреть разбор");
    if (playIcon) playIcon.textContent = state.autoplay ? "◼" : "▶";
    if (shell) shell.classList.toggle("is-playing", state.autoplay);
  }

  function stopAutoplay(): void {
    state.autoplay = false;
    clearAuto();
    updatePlayUI();
    if (shell) shell.classList.remove("is-playing");
  }

  function startAutoplay(): void {
    if (paused()) {
      setStep(1);
      return;
    }
    if (state.step === 5) setStep(1);
    state.autoplay = true;
    if (shell) {
      shell.classList.remove("is-playing");
      void shell.offsetWidth;
      shell.classList.add("is-playing");
    }
    updatePlayUI();
    scheduleAuto();
  }

  function setStep(next: number | string, options: StepOptions = {}) {
    const number = Math.max(1, Math.min(5, Number(next) || 1));
    if (number === state.step && !options.force) {
      if (options.focus) {
        const currentTab = tabs.find((tab) => Number(tab.dataset.step) === number);
        if (currentTab) currentTab.focus();
      }
      return;
    }
    const previous = state.step;
    state.step = number;
    state.visited.add(number);

    tabs.forEach((tab) => {
      const isActive = Number(tab.dataset.step) === number;
      tab.classList.toggle("is-active", isActive);
      tab.classList.toggle("is-visited", state.visited.has(Number(tab.dataset.step)));
      tab.setAttribute("aria-selected", String(isActive));
      tab.tabIndex = isActive ? 0 : -1;
    });

    views.forEach((view) => {
      const isActive = Number(view.dataset.stepView) === number;
      view.hidden = !isActive;
      view.classList.toggle("is-active", isActive);
    });

    progressBars.forEach((bar, index) => {
      bar.classList.toggle("is-done", index < number - 1);
      bar.classList.toggle("is-current", index === number - 1);
    });

    if (options.updateUrl !== false) {
      const url = new URL(window.location.href);
      if (url.searchParams.get("step") !== String(number)) {
        url.searchParams.set("step", String(number));
        if (options.history === "push") {
          window.history.pushState({ step: number }, "", url);
        } else {
          window.history.replaceState({ step: number }, "", url);
        }
      }
    }

    if (stepCurrent) stepCurrent.textContent = String(number).padStart(2, "0");
    if (stepTitle) stepTitle.textContent = stepData[number].title;
    if (stepOutput) stepOutput.textContent = stepData[number].output;

    if (prevButton) prevButton.disabled = number === 1;
    if (nextButton) nextButton.disabled = number === 5;
    if (executeButton) {
      const label = number === 5 ? "Начать заново" : "Следующий шаг";
      if (executeButton.firstChild) executeButton.firstChild.nodeValue = label + " ";
    }

    if (options.focus) {
      const activeTab = tabs.find((tab) => Number(tab.dataset.step) === number);
      if (activeTab) activeTab.focus();
    }

    // Reset the per-step progress animation when autoplay is active.
    if (shell && state.autoplay) {
      shell.classList.remove("is-playing");
      void shell.offsetWidth;
      shell.classList.add("is-playing");
    }

    if (options.fromAuto) {
      scheduleAuto();
    } else if (state.autoplay) {
      scheduleAuto();
    }

    // Small screen: keep the active tab visible in the horizontal rail.
    const activeTab = tabs.find((tab) => Number(tab.dataset.step) === number);
    if (activeTab && window.innerWidth <= 1060 && !options.initial) {
      activeTab.scrollIntoView({ block: "nearest", inline: "nearest", behavior: paused() ? "auto" : "smooth" });
    }

    if (previous !== number && !options.fromAuto && state.autoplay) scheduleAuto();
  }

  if (tabs.length && views.length) {
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => setStep(tab.dataset.step ?? 1, { history: "push" }));
    });

    const tablist = $(".demo-steps");
    if (tablist) {
      tablist.addEventListener("keydown", (event) => {
        const key = event.key;
        const current = tabs.findIndex((tab) => Number(tab.dataset.step) === state.step);
        let target = -1;
        if (key === "ArrowRight" || key === "ArrowDown") target = (current + 1) % tabs.length;
        else if (key === "ArrowLeft" || key === "ArrowUp") target = (current - 1 + tabs.length) % tabs.length;
        else if (key === "Home") target = 0;
        else if (key === "End") target = tabs.length - 1;
        else return;
        event.preventDefault();
        setStep(tabs[target]?.dataset.step ?? 1, { focus: true, history: "push" });
      });
    }

    if (prevButton) prevButton.addEventListener("click", () => setStep(state.step - 1, { history: "push" }));
    if (nextButton) nextButton.addEventListener("click", () => setStep(state.step + 1, { history: "push" }));
    if (executeButton) {
      executeButton.addEventListener("click", () => {
        if (state.step >= 5) setStep(1, { history: "push" });
        else setStep(state.step + 1, { history: "push" });
      });
    }

    $$("[data-go-step]").forEach((button) => {
      button.addEventListener("click", () => setStep(button.dataset.goStep ?? 1, { history: "push" }));
    });

    if (playButton) {
      playButton.addEventListener("click", () => {
        if (state.autoplay) stopAutoplay();
        else startAutoplay();
      });
    }

    const requestedStep = Number(new URLSearchParams(window.location.search).get("step"));
    const initialStep = Number.isInteger(requestedStep) && requestedStep >= 1 && requestedStep <= 5 ? requestedStep : 1;
    setStep(initialStep, { force: true, initial: true, updateUrl: false });
    updatePlayUI();

    window.addEventListener("popstate", () => {
      const next = Number(new URLSearchParams(window.location.search).get("step"));
      if (Number.isInteger(next) && next >= 1 && next <= 5) {
        setStep(next, { force: true, updateUrl: false });
      }
    }, { signal: ac.signal });

    document.addEventListener("visibilitychange", () => {
      if (document.hidden && state.autoplay) stopAutoplay();
    }, { signal: ac.signal });

    if (typeof reduceQuery.addEventListener === "function") {
      reduceQuery.addEventListener("change", () => {
        if (reduceMotion() && state.autoplay) stopAutoplay();
      }, { signal: ac.signal });
    }
  }

  /* -------------------------------------------------------
     Step 2 — extracted fields and source trace
     ------------------------------------------------------- */

  const extractRows = $$("[data-extract]");
  const sourceLines = $$("[data-source-line]");
  if (extractRows.length) {
    extractRows.forEach((row) => {
      row.addEventListener("click", () => {
        const id = row.dataset.extract;
        extractRows.forEach((item) => {
          const active = item === row;
          item.classList.toggle("is-active", active);
          item.setAttribute("aria-pressed", String(active));
        });
        sourceLines.forEach((line) => {
          line.classList.toggle("is-active", line.dataset.sourceLine === id);
        });
      });
    });
  }

  /* -------------------------------------------------------
     Step 3 — candidates filter and details
     ------------------------------------------------------- */

  const filterButtons = $$("[data-supplier-filter]");
  const supplierCards = $$(".supplier-card");
  if (filterButtons.length && supplierCards.length) {
    filterButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const filter = button.dataset.supplierFilter;
        filterButtons.forEach((item) => {
          const active = item === button;
          item.classList.toggle("is-active", active);
          item.setAttribute("aria-pressed", String(active));
        });
        supplierCards.forEach((card) => {
          card.hidden = filter !== "all" && card.dataset.role !== filter;
        });
      });
    });
    supplierCards.forEach((card) => {
      const toggle = $(".supplier-card__toggle", card);
      const more = $(".supplier-card__more", card);
      if (!toggle || !more) return;
      toggle.addEventListener("click", () => {
        const open = toggle.getAttribute("aria-expanded") !== "true";
        toggle.setAttribute("aria-expanded", String(open));
        more.hidden = !open;
      });
    });
  }

  /* -------------------------------------------------------
     Step 4 — only differences
     ------------------------------------------------------- */

  const diffToggle = $("[data-diff-toggle]");
  if (diffToggle) {
    diffToggle.addEventListener("click", () => {
      const onlyDiff = diffToggle.getAttribute("aria-pressed") !== "true";
      diffToggle.setAttribute("aria-pressed", String(onlyDiff));
      $$(".diff-table tbody tr").forEach((row) => {
        row.classList.toggle("is-hidden", onlyDiff && row.dataset.diff === "same");
      });
    });
  }

  /* -------------------------------------------------------
     Step 5 — copy and download the RFQ draft
     ------------------------------------------------------- */

  const rfqText = [
    "Добрый день!",
    "",
    "Просим предоставить коммерческое предложение на поставку:",
    "1. Кабель ВВГнг(А)-LS 3×2,5, ГОСТ 31996-2012 — 1 000 м, поставка в Казань.",
    "",
    "Просим указать наличие, цену с НДС, срок поставки и стоимость доставки. Приложите паспорт качества и документы о соответствии.",
    "",
    "С уважением, отдел снабжения."
  ].join("\n");
  const copyButton = $("[data-copy-rfq]");
  const copyStatus = $("[data-copy-status]");
  const downloadButton = $("[data-download-rfq]");
  let copyTimer = 0;

  function showCopyStatus(text: string, error = false): void {
    if (!copyStatus) return;
    copyStatus.textContent = text;
    copyStatus.classList.toggle("is-error", error);
    window.clearTimeout(copyTimer);
    copyTimer = window.setTimeout(() => {
      copyStatus.textContent = "";
      copyStatus.classList.remove("is-error");
    }, 3200);
  }

  async function copyText(text: string): Promise<boolean> {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.className = "copy-buffer";
      scope!.appendChild(area);
      area.select();
      const ok = document.execCommand("copy");
      area.remove();
      return ok;
    } catch {
      return false;
    }
  }

  if (copyButton) {
    copyButton.addEventListener("click", async () => {
      const copied = await copyText(rfqText);
      showCopyStatus(copied ? "Скопировано" : "Не удалось скопировать", !copied);
    });
  }

  if (downloadButton) {
    downloadButton.addEventListener("click", () => {
      try {
        const blob = new Blob([rfqText], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = "tenderlex-zapros-kp-primer.txt";
        scope!.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      } catch {
        showCopyStatus("Скачивание недоступно", true);
      }
    });
  }

  /* -------------------------------------------------------
     Quick self-check
     ------------------------------------------------------- */

  const quizOptions = $$("[data-quiz-option]");
  const quizFeedback = $("[data-quiz-feedback]");
  if (quizOptions.length && quizFeedback) {
    const quizMessages = {
      quantity: "Количество уже есть в позиции: 1 000 м. Перечитайте черновик — какого условия в нём нет?",
      address: "Адрес поставки указан: Казань. Найдите условие, которого в письме нет.",
      payment: "Верно. В черновике нет срока оплаты — это вопрос к закупке и поставщику. Добавьте его до отправки."
    };
    quizOptions.forEach((option) => {
      option.addEventListener("click", () => {
        const answer = option.dataset.quizOption;
        quizOptions.forEach((item) => {
          item.classList.remove("is-correct", "is-wrong");
          item.setAttribute("aria-pressed", "false");
        });
        option.setAttribute("aria-pressed", "true");
        const correct = answer === "payment";
        option.classList.add(correct ? "is-correct" : "is-wrong");
        quizFeedback.textContent = (answer && quizMessages[answer as keyof typeof quizMessages]) || "";
        quizFeedback.classList.toggle("is-correct", correct);
        quizFeedback.classList.toggle("is-wrong", !correct);
      });
    });
  }

  /* -------------------------------------------------------
     FAQ accordion
     ------------------------------------------------------- */

  const faqButtons = $$("[data-faq]");
  if (faqButtons.length) {
    const closeFaq = (button: HTMLElement) => {
      const answer = document.getElementById(button.getAttribute("aria-controls") ?? "");
      const item = button.closest(".faq-item");
      button.setAttribute("aria-expanded", "false");
      if (item) item.classList.remove("is-open");
      if (answer) {
        window.setTimeout(() => {
          if (button.getAttribute("aria-expanded") === "false") answer.hidden = true;
        }, 320);
      }
    };
    const openFaq = (button: HTMLElement) => {
      const answer = document.getElementById(button.getAttribute("aria-controls") ?? "");
      const item = button.closest(".faq-item");
      button.setAttribute("aria-expanded", "true");
      if (item) item.classList.add("is-open");
      if (answer) answer.hidden = false;
    };

    faqButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const isOpen = button.getAttribute("aria-expanded") === "true";
        faqButtons.forEach((other) => {
          if (other !== button && other.getAttribute("aria-expanded") === "true") closeFaq(other);
        });
        if (isOpen) closeFaq(button);
        else openFaq(button);
      });
    });
  }

  /* -------------------------------------------------------
     Role tabs
     ------------------------------------------------------- */

  const roleTabs = $$("[data-role-tab]");
  const rolePanels = $$("[data-role-panel]");
  if (roleTabs.length && rolePanels.length) {
    const setRole = (number: number, focus = false) => {
      roleTabs.forEach((tab) => {
        const active = Number(tab.dataset.roleTab) === number;
        tab.classList.toggle("is-active", active);
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        if (active && focus) tab.focus();
      });
      rolePanels.forEach((panel) => {
        const active = Number(panel.dataset.rolePanel) === number;
        panel.hidden = !active;
        panel.classList.toggle("is-active", active);
      });
    };

    roleTabs.forEach((tab) => {
      tab.addEventListener("click", () => setRole(Number(tab.dataset.roleTab)));
    });

    const tablist = $(".roles__tabs");
    if (tablist) {
      tablist.addEventListener("keydown", (event) => {
        const activeRole = $(".role-tab.is-active");
        const current = activeRole ? roleTabs.indexOf(activeRole) : 0;
        let target = -1;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") target = (current + 1) % roleTabs.length;
        else if (event.key === "ArrowLeft" || event.key === "ArrowUp") target = (current - 1 + roleTabs.length) % roleTabs.length;
        else if (event.key === "Home") target = 0;
        else if (event.key === "End") target = roleTabs.length - 1;
        else return;
        event.preventDefault();
        setRole(Number(roleTabs[target].dataset.roleTab), true);
      });
    }
  }


    if (reduceMotion() && state.autoplay) stopAutoplay();

    (window as Window & { __TENDERLEX_HOME_V3__?: unknown }).__TENDERLEX_HOME_V3__ = {
      get step() { return state.step; },
      get autoplay() { return state.autoplay; },
      get reducedMotion() { return reduceMotion(); }
    };

    return () => {
      ac.abort();
      revealObserver?.disconnect();
      if (revealFallback) window.clearTimeout(revealFallback);
      stopAutoplay();
      if (copyTimer) window.clearTimeout(copyTimer);
      delete (window as Window & { __TENDERLEX_HOME_V3__?: unknown }).__TENDERLEX_HOME_V3__;
    };
  }, []);
  return null;
}
