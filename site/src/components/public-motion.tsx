"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";

const REVEAL_SELECTOR = [
  "section:not(.tl-hero)",
  "article",
  ".tl-tool",
  ".tl-demo",
  ".tl-packages a",
  ".tl-card",
  ".tl-feature-card",
  ".tl-region-card",
].join(", ");

const HERO_SELECTOR =
  ".tl-hero .tl-eyebrow, .tl-hero .tl-actions, .tl-hero .tl-proof, .tl-hero .tl-demo";
const MOTION_QUERY = "(prefers-reduced-motion: reduce)";
const EASING = "cubic-bezier(0.22, 1, 0.36, 1)";

/**
 * Adds low-cost, one-shot Web Animations only after hydration. Content keeps
 * its final visible CSS state when JavaScript is unavailable or motion is off.
 */
export function PublicMotion() {
  const pathname = usePathname();

  useEffect(() => {
    if (pathname === "/cabinet" || pathname.startsWith("/cabinet/")) {
      return;
    }

    if (!document.querySelector(".tl-site-header")) {
      return;
    }

    // Home v3 owns its reveal/motion system; keep the legacy public motion off.
    if (document.querySelector(".home-v3")) {
      return;
    }

    const publicMain = document.querySelector<HTMLElement>("main");
    if (!publicMain) return;

    const motionQuery = window.matchMedia(MOTION_QUERY);
    const candidates = Array.from(
      publicMain.querySelectorAll<HTMLElement>(REVEAL_SELECTOR),
    )
      .filter((element) => !element.closest(".tl-hero"))
      .filter((element) => !element.querySelector("h1"));
    // A card is more useful as a reveal target than its enclosing grid section.
    // Keeping leaf candidates prevents a parent and its child from moving twice.
    const targets = candidates.filter(
      (element) =>
        !candidates.some(
          (candidate) => candidate !== element && element.contains(candidate),
        ),
    );
    const heroTargets = Array.from(
      publicMain.querySelectorAll<HTMLElement>(HERO_SELECTOR),
    );
    let observer: IntersectionObserver | undefined;
    let frame = 0;
    const animations = new Set<Animation>();
    const revealed = new Set<HTMLElement>();

    const stop = () => {
      window.cancelAnimationFrame(frame);
      observer?.disconnect();
      observer = undefined;
      animations.forEach((animation) => animation.cancel());
      animations.clear();
      revealed.clear();
      publicMain.classList.remove("tl-motion-scope");
    };

    const reveal = (element: HTMLElement, delay = 0) => {
      if (
        motionQuery.matches ||
        revealed.has(element) ||
        typeof element.animate !== "function"
      )
        return;
      revealed.add(element);
      const animation = element.animate(
        [
          { opacity: 0.82, transform: "translateY(12px)" },
          { opacity: 1, transform: "translateY(0)" },
        ],
        { duration: 420, delay, easing: EASING },
      );
      animations.add(animation);
      animation.addEventListener("finish", () => animations.delete(animation), {
        once: true,
      });
      animation.addEventListener("cancel", () => animations.delete(animation), {
        once: true,
      });
      observer?.unobserve(element);
    };

    const start = () => {
      if (motionQuery.matches) {
        stop();
        return;
      }

      stop();
      publicMain.classList.add("tl-motion-scope");

      const nearViewport = targets.filter((element) => {
        const { top, bottom } = element.getBoundingClientRect();
        return bottom > -80 && top < window.innerHeight + 120;
      });

      frame = window.requestAnimationFrame(() => {
        heroTargets.forEach((element, index) => reveal(element, index * 70));
        nearViewport.forEach((element, index) =>
          reveal(element, (index % 4) * 45),
        );
      });

      if (!("IntersectionObserver" in window)) {
        targets.forEach((element, index) => reveal(element, (index % 4) * 45));
        return;
      }

      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              reveal(entry.target as HTMLElement);
            }
          });
        },
        { root: null, rootMargin: "0px 0px -9%", threshold: 0.08 },
      );

      targets.forEach((element) => {
        if (!revealed.has(element)) {
          observer?.observe(element);
        }
      });
    };

    start();
    const handlePreferenceChange = () => start();
    motionQuery.addEventListener("change", handlePreferenceChange);

    return () => {
      motionQuery.removeEventListener("change", handlePreferenceChange);
      stop();
    };
  }, [pathname]);

  return null;
}
