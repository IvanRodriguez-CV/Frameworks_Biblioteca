import { initAuth } from "./auth.js";
import { initCatalog } from "./catalog.js";
import { initLoans } from "./loans.js";
import { initManagement } from "./management.js";

const loginMessage = document.querySelector("#login-message");
const publicSite = document.querySelector("#public-site");
const adminDashboard = document.querySelector("#admin-dashboard");

function showMessage(message, isError = false) {
  loginMessage.textContent = message;
  loginMessage.classList.toggle("message-error", isError);
}

function showAdminMessage(message, isError = false) {
  management.showError(message, isError);
}

const loans = initLoans(showMessage);
const catalog = initCatalog(showMessage, loans.load);
const management = initManagement(showMessage, catalog.refreshAvailability);
loans.setAvailabilityRefresh(catalog.refreshAvailability);

initAuth({
  showMessage,
  loadLoans: loans.load,
  onLoginStart() {
    catalog.setAuthenticated(true);
    management.setCurrentUser(null);
    management.clear();
    publicSite.hidden = false;
    adminDashboard.hidden = true;
  },
  async onAuthenticated(user) {
    management.setCurrentUser(user);
    const canManage = ["admin", "librarian"].includes(user.role);
    if (canManage) {
      document.querySelector("#admin-session-message").textContent =
        `Sesión iniciada como ${user.username}.`;
      publicSite.hidden = true;
      adminDashboard.hidden = false;
      try {
        await management.load();
      } catch (error) {
        showAdminMessage(`No se pudo cargar la administración: ${error.message}`, true);
      }
    } else {
      publicSite.hidden = false;
      adminDashboard.hidden = true;
    }
  },
  onLogout() {
    catalog.setAuthenticated(false);
    loans.clear();
    management.clear();
    publicSite.hidden = false;
    adminDashboard.hidden = true;
  },
});
