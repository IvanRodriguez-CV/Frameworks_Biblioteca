import { apiRequest, fetchAll } from "./api.js";
import { displayRole, displayStatus, resources } from "./management-config.js";

export function initManagement(showMessage, refreshAvailability) {
  const managementResource = document.querySelector("#management-resource");
  const managementForm = document.querySelector("#management-form");
  const managementFields = document.querySelector("#management-fields");
  const managementList = document.querySelector("#management-list");
  const managementMessage = document.querySelector("#management-message");
  let currentUser = null;
  let managedRecords = [];
  let managerData = {};
  let loadId = 0;

  function showManagementMessage(message, isError = false) {
    managementMessage.textContent = message;
    managementMessage.classList.toggle("message-error", isError);
  }

  function selectedResource() {
    return resources[managementResource.value];
  }

  function makeAction(label, action, id, extraClass = "") {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `management-action ${extraClass}`.trim();
    button.dataset.managementAction = action;
    button.dataset.recordId = id;
    button.textContent = label;
    return button;
  }

  function recordDescription(record, resource) {
    if (resource === "books") {
      return `${record.author_name || ""}${record.publication_year ? ` · ${record.publication_year}` : ""} · ${record.available_copies} de ${record.copies_count} disponibles`;
    }
    if (resource === "authors") return record.biography || "Autor";
    if (resource === "categories") return record.description || "Categoría";
    if (resource === "copies") return `${record.book_title} · ${displayStatus(record.status)} · ${record.inventory_code}`;
    if (resource === "users") return `${record.email} · ${displayRole(record.role)} · ${record.is_active ? "Activa" : "Desactivada"}`;
    return `${record.username} · ${record.inventory_code} · Devolver antes del ${record.due_date} · ${displayStatus(record.status)}`;
  }

  function renderManagement(records) {
    const resource = managementResource.value;
    managementList.replaceChildren();
    if (!records.length) {
      const empty = document.createElement("p");
      empty.textContent = `No hay ${resources[resource].label} para mostrar.`;
      managementList.append(empty);
      return;
    }

    for (const record of records) {
      const item = document.createElement("article");
      item.className = "management-item";
      const details = document.createElement("div");
      const title = document.createElement("h3");
      title.textContent = resource === "books" ? record.title
        : resource === "authors" || resource === "categories" ? record.name
          : resource === "users" ? record.username : record.book_title;
      const description = document.createElement("p");
      description.textContent = recordDescription(record, resource);
      details.append(title, description);
      item.append(details);

      const actions = document.createElement("div");
      actions.className = "management-actions";
      const isOwnAccount = resource === "users" && record.id === currentUser?.id;
      if (resources[resource].canEdit !== false && !isOwnAccount) {
        actions.append(makeAction("Editar", "edit", record.id));
      }
      if (resource === "users" && !isOwnAccount) {
        actions.append(makeAction(record.is_active ? "Desactivar" : "Activar", "toggle", record.id));
      }
      if (resources[resource].canDelete !== false && !isOwnAccount) {
        actions.append(makeAction("Eliminar", "delete", record.id, "danger"));
      }
      if (resource === "loans" && record.status === "active") {
        actions.append(makeAction("Registrar devolución", "return", record.id));
      }
      if (actions.childElementCount) item.append(actions);
      managementList.append(item);
    }
  }

  async function load() {
    const requestId = ++loadId;
    const resourceName = managementResource.value;
    const resource = selectedResource();
    managedRecords = [];
    managementList.replaceChildren();
    const loading = document.createElement("p");
    loading.textContent = "Cargando...";
    managementList.append(loading);
    managementList.setAttribute("aria-busy", "true");
    try {
      const records = await fetchAll(resource.endpoint);
      if (resourceName === "books") {
        const authors = await fetchAll("/api/authors/");
        const authorNames = new Map(authors.map((author) => [author.id, author.name]));
        records.forEach((book) => { book.author_name = authorNames.get(book.author) || ""; });
      }
      if (requestId !== loadId) return;
      managedRecords = records;
      renderManagement(managedRecords);
      showManagementMessage("");
    } catch (error) {
      if (requestId !== loadId) return;
      managementList.replaceChildren();
      throw error;
    } finally {
      if (requestId === loadId) managementList.removeAttribute("aria-busy");
    }
  }

  function resetForm() {
    managementForm.reset();
    managementForm.hidden = true;
    delete managementForm.dataset.recordId;
  }

  function createField(field, record) {
    const wrapper = document.createElement("label");
    wrapper.className = field.type === "checkbox" ? "management-checkbox" : "management-field";
    const caption = document.createElement("span");
    caption.textContent = field.label;
    wrapper.append(caption);

    let input;
    if (field.type === "textarea") {
      input = document.createElement("textarea");
      input.rows = 3;
    } else if (field.type === "select") {
      input = document.createElement("select");
      const emptyOption = document.createElement("option");
      emptyOption.value = "";
      emptyOption.textContent = "Selecciona una opción";
      input.append(emptyOption);
      const options = field.options || (field.source === "authors"
        ? managerData.authors
        : field.source === "categories" ? managerData.categories
          : field.source === "books" ? managerData.books
            : field.source === "copies" ? managerData.copies : managerData.users);
      for (const option of options || []) {
        const element = document.createElement("option");
        element.value = field.options ? option[0] : option.id;
        element.textContent = field.options
          ? option[1]
          : field.source === "authors" || field.source === "categories" ? option.name
            : field.source === "books" ? option.title
              : field.source === "copies" ? `${option.inventory_code} · ${option.book_title} (${displayStatus(option.status)})`
                : option.username;
        if (field.source === "users" && !option.is_active) continue;
        if (field.source === "copies" && option.status !== "available") element.disabled = true;
        element.selected = String(element.value) === String(record?.[field.name] ?? "");
        input.append(element);
      }
    } else if (field.type === "checkbox") {
      input = document.createElement("input");
      input.type = "checkbox";
      input.checked = record ? Boolean(record[field.name]) : Boolean(field.defaultValue);
    } else {
      input = document.createElement("input");
      input.type = field.type || "text";
      if (field.min !== undefined) input.min = field.min;
      if (field.max !== undefined) input.max = field.max;
    }

    input.name = field.name;
    input.dataset.field = field.name;
    input.required = Boolean(field.required || (!record && field.requiredOnCreate));
    if (field.type !== "checkbox" && record?.[field.name] !== undefined && record[field.name] !== null) {
      input.value = record[field.name];
    }
    if (field.name === "password" && record) {
      input.required = false;
      input.placeholder = "Déjala vacía para conservarla";
    }
    wrapper.append(input);
    return wrapper;
  }

  async function openForm(record = null) {
    const resource = selectedResource();
    const fields = resource.fields.filter((field) => field.name !== "initial_copies" || !record);
    managementFields.replaceChildren();
    if (fields.some((field) => field.type === "select" && field.source)) {
      managerData = {
        authors: await fetchAll("/api/authors/"),
        categories: await fetchAll("/api/categories/"),
        books: await fetchAll("/api/books/"),
        copies: await fetchAll("/api/copies/"),
        users: await fetchAll("/api/users/"),
      };
    }
    fields.forEach((field) => managementFields.append(createField(field, record)));
    managementForm.dataset.recordId = record ? record.id : "";
    managementForm.hidden = false;
    managementForm.scrollIntoView({ behavior: "smooth", block: "nearest" });
    showManagementMessage(record ? "Editando registro." : "Completa los datos para registrar.");
  }

  document.querySelector("#management-new").addEventListener("click", () => {
    openForm().catch((error) => showManagementMessage(error.message, true));
  });
  document.querySelector("#management-cancel").addEventListener("click", resetForm);
  managementResource.addEventListener("change", () => {
    resetForm();
    load().catch((error) => showManagementMessage(error.message, true));
  });
  managementList.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-management-action]");
    if (!button) return;
    const record = managedRecords.find((item) => item.id === Number(button.dataset.recordId));
    if (!record) return;
    button.disabled = true;
    try {
      const action = button.dataset.managementAction;
      const endpoint = `${selectedResource().endpoint}${record.id}/`;
      if (action === "edit") {
        await openForm(record);
      } else if (action === "toggle") {
        await apiRequest(endpoint, {
          method: "PATCH",
          body: JSON.stringify({ is_active: !record.is_active }),
        });
        showManagementMessage(record.is_active ? "Cuenta desactivada." : "Cuenta activada.");
        await load();
      } else if (action === "delete") {
        if (!window.confirm("¿Seguro que deseas eliminar este registro? Esta acción no se puede deshacer.")) return;
        await apiRequest(endpoint, { method: "DELETE" });
        showManagementMessage("Registro eliminado.");
        await load();
      } else if (action === "return") {
        await apiRequest(`/api/loans/${record.id}/return/`, { method: "POST" });
        showManagementMessage("Devolución registrada.");
        await load();
        try {
          await refreshAvailability();
        } catch (error) {
          showManagementMessage(`Devolución registrada, pero no se pudo actualizar la disponibilidad: ${error.message}`, true);
        }
      }
    } catch (error) {
      showManagementMessage(error.message, true);
    } finally {
      button.disabled = false;
    }
  });
  managementForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const resource = selectedResource();
    const recordId = managementForm.dataset.recordId;
    const payload = {};
    for (const field of resource.fields) {
      if (field.name === "initial_copies" && recordId) continue;
      const input = managementForm.elements.namedItem(field.name);
      if (!input) continue;
      if (field.type === "checkbox") {
        payload[field.name] = input.checked;
      } else if (field.type === "number") {
        if (input.value !== "") payload[field.name] = Number(input.value);
      } else if (input.value !== "") {
        payload[field.name] = field.type === "select" && field.source ? Number(input.value) : input.value;
      } else if (field.required || (!recordId && field.requiredOnCreate)) {
        input.reportValidity();
        return;
      }
    }

    const saveButton = managementForm.querySelector("button[type='submit']");
    saveButton.disabled = true;
    showManagementMessage("");
    try {
      const endpoint = recordId ? `${resource.endpoint}${recordId}/` : resource.endpoint;
      await apiRequest(endpoint, {
        method: recordId ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      resetForm();
      await load();
      showManagementMessage(recordId ? "Cambios guardados." : "Registro creado.");
      if (!recordId && managementResource.value === "loans") {
        try {
          await refreshAvailability();
        } catch (error) {
          showManagementMessage(`Préstamo registrado, pero no se pudo actualizar la disponibilidad: ${error.message}`, true);
        }
      }
      if (["books", "copies", "authors", "categories"].includes(managementResource.value)) {
        showMessage("Cambios guardados. Recarga la página para actualizar el catálogo público.");
      }
    } catch (error) {
      showManagementMessage(error.message, true);
    } finally {
      saveButton.disabled = false;
    }
  });

  return {
    load,
    showError: showManagementMessage,
    setCurrentUser(user) {
      currentUser = user;
    },
    clear() {
      loadId += 1;
      currentUser = null;
      managedRecords = [];
      managerData = {};
      resetForm();
      managementList.replaceChildren();
      managementList.removeAttribute("aria-busy");
      showManagementMessage("");
    },
  };
}
