import { apiRequest, fetchAll } from "./api.js";

export function initCatalog(showMessage, loadLoans) {
  const bookGrid = document.querySelector(".book-grid");
  let isAuthenticated = false;

  function updateBookAvailability(card, copies) {
    const availableCopies = copies.filter((copy) => copy.status === "available");
    const availability = card.querySelector(".availability");
    const availabilityText = availability.querySelector(".availability-text");
    availability.classList.toggle("unavailable", availableCopies.length === 0);
    availabilityText.textContent = availableCopies.length
      ? `${availableCopies.length} disponible${availableCopies.length === 1 ? "" : "s"}`
      : "Sin ejemplares disponibles";

    let button = card.querySelector(".borrow-button");
    if (!availableCopies.length) {
      button?.remove();
      return;
    }

    if (!button) {
      button = document.createElement("button");
      button.className = "borrow-button";
      button.type = "button";
      button.textContent = "Pedir préstamo ";
      button.dataset.authenticated = String(isAuthenticated);
      const arrow = document.createElement("span");
      arrow.setAttribute("aria-hidden", "true");
      arrow.textContent = "→";
      button.append(arrow);
      card.querySelector(".book-info").append(button);
    }
    button.dataset.copyId = availableCopies[0].id;
  }

  async function refreshAvailability() {
    if (!document.querySelector("#access-session") || document.querySelector("#access-session").hidden) return;
    const copies = await fetchAll("/api/copies/");
    const copiesByBook = new Map();
    for (const copy of copies) {
      const bookCopies = copiesByBook.get(copy.book) || [];
      bookCopies.push(copy);
      copiesByBook.set(copy.book, bookCopies);
    }
    document.querySelectorAll(".book-card[data-book-id]").forEach((card) => {
      updateBookAvailability(card, copiesByBook.get(Number(card.dataset.bookId)) || []);
    });
  }

  if (bookGrid) {
    bookGrid.addEventListener("click", async (event) => {
      const button = event.target.closest(".borrow-button");
      if (!button) return;
      if (button.dataset.authenticated !== "true") {
        document.querySelector("#acceso").scrollIntoView({ behavior: "smooth" });
        showMessage("Inicia sesión para pedir este libro.");
        document.querySelector("#login-username").focus({ preventScroll: true });
        return;
      }

      button.disabled = true;
      try {
        await apiRequest("/api/loans/", {
          method: "POST",
          body: JSON.stringify({ copy: Number(button.dataset.copyId) }),
        });
        showMessage("¡Préstamo registrado! Ya aparece en tus préstamos.");
        const card = button.closest(".book-card");
        button.remove();
        card.querySelector(".availability-text").textContent = "Actualizando disponibilidad...";
        try {
          await refreshAvailability();
        } catch (error) {
          showMessage(`Préstamo registrado, pero no se pudo actualizar la disponibilidad: ${error.message}`, true);
        }
        try {
          await loadLoans();
        } catch (error) {
          showMessage(`Préstamo registrado, pero no se pudieron cargar tus préstamos: ${error.message}`, true);
        }
      } catch (error) {
        showMessage(error.message, true);
      } finally {
        if (button.isConnected) button.disabled = false;
      }
    });
  }

  return {
    setAuthenticated(authenticated) {
      isAuthenticated = authenticated;
      document.querySelectorAll(".borrow-button").forEach((button) => {
        button.dataset.authenticated = String(authenticated);
      });
    },
    refreshAvailability,
  };
}
