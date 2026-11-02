document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".metric-card, .feature-card, .book-card").forEach((card) => {
    card.addEventListener("mouseenter", () => card.classList.add("is-hovered"));
    card.addEventListener("mouseleave", () => card.classList.remove("is-hovered"));
  });
});
