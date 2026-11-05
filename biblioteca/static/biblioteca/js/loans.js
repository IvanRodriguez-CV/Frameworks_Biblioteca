import { apiRequest } from "./api.js";

export function initLoans(showMessage) {
  const loansSection = document.querySelector("#mis-prestamos");
  const loansList = document.querySelector("#loans-list");
  let refreshAvailability = async () => {};

  function render(loans) {
    loansList.replaceChildren();
    if (!loans.length) {
      const empty = document.createElement("p");
      empty.className = "book-author";
      empty.textContent = "Todavía no tienes préstamos activos.";
      loansList.append(empty);
      return;
    }

    for (const loan of loans) {
      const item = document.createElement("article");
      item.className = "loan-item";
      const description = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = loan.book_title;
      const copy = document.createElement("p");
      copy.textContent = `Ejemplar ${loan.inventory_code} · Devolver antes del ${loan.due_date}`;
      const returnButton = document.createElement("button");
      returnButton.className = "return-button";
      returnButton.dataset.loanId = loan.id;
      returnButton.type = "button";
      returnButton.textContent = "Devolver";
      description.append(title, copy);
      item.append(description, returnButton);
      loansList.append(item);
    }
  }

  async function load() {
    const data = await apiRequest("/api/loans/active/");
    render(data.results || data);
    loansSection.hidden = false;
  }

  loansList.addEventListener("click", async (event) => {
    const button = event.target.closest(".return-button");
    if (!button) return;

    button.disabled = true;
    try {
      await apiRequest(`/api/loans/${Number(button.dataset.loanId)}/return/`, { method: "POST" });
      showMessage("Devolución registrada. ¡Gracias por regresar el libro!");
      await load();
      try {
        await refreshAvailability();
      } catch (error) {
        showMessage(`Devolución registrada, pero no se pudo actualizar la disponibilidad: ${error.message}`, true);
      }
    } catch (error) {
      showMessage(error.message, true);
    } finally {
      button.disabled = false;
    }
  });

  return {
    load,
    setAvailabilityRefresh(refresh) {
      refreshAvailability = refresh;
    },
    clear() {
      loansSection.hidden = true;
      loansList.replaceChildren();
    },
  };
}
