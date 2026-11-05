import { apiRequest, readJson, setAccessToken } from "./api.js";

export function initAuth({ showMessage, loadLoans, onLoginStart, onAuthenticated, onLogout }) {
  const loginForm = document.querySelector("#login-form");
  const registerForm = document.querySelector("#register-form");
  const loginButton = loginForm.querySelector("button[type='submit']");
  const registerButton = registerForm.querySelector("button[type='submit']");
  const accessSession = document.querySelector("#access-session");

  function showLogin() {
    loginForm.hidden = false;
    registerForm.hidden = true;
    document.querySelector("#login-switch").hidden = false;
    document.querySelector("#register-switch").hidden = true;
    showMessage("");
  }

  document.querySelector("#show-register").addEventListener("click", () => {
    loginForm.hidden = true;
    registerForm.hidden = false;
    document.querySelector("#login-switch").hidden = true;
    document.querySelector("#register-switch").hidden = false;
    showMessage("");
    document.querySelector("#register-username").focus();
  });
  document.querySelector("#show-login").addEventListener("click", showLogin);

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    registerButton.disabled = true;
    showMessage("");
    try {
      const formData = new FormData(registerForm);
      await fetch("/api/auth/register/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: formData.get("username"),
          email: formData.get("email"),
          password: formData.get("password"),
        }),
      }).then(readJson);
      registerForm.reset();
      showLogin();
      showMessage("Cuenta creada. Ya puedes iniciar sesión.");
    } catch (error) {
      showMessage(error.message, true);
    } finally {
      registerButton.disabled = false;
    }
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginButton.disabled = true;
    showMessage("");
    try {
      const formData = new FormData(loginForm);
      const tokenData = await fetch("/api/auth/token/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: formData.get("username"),
          password: formData.get("password"),
        }),
      }).then(readJson);

      setAccessToken(tokenData.access);
      onLoginStart();
      loginForm.hidden = true;
      registerForm.hidden = true;
      document.querySelector("#login-switch").hidden = true;
      document.querySelector("#register-switch").hidden = true;
      accessSession.hidden = false;
      document.querySelector("#session-message").textContent =
        `Sesión iniciada como ${formData.get("username")}.`;
      loginForm.reset();
      showMessage("¡Listo! Ya puedes solicitar ejemplares.");

      try {
        await loadLoans();
      } catch (error) {
        showMessage(`Sesión iniciada; no se pudieron cargar tus préstamos: ${error.message}`, true);
      }

      let user;
      try {
        user = await apiRequest("/api/auth/me/");
      } catch (error) {
        showMessage(`Sesión iniciada; no se pudo cargar tu perfil: ${error.message}`, true);
        return;
      }
      await onAuthenticated(user);
    } catch (error) {
      setAccessToken("");
      showMessage(error.message, true);
    } finally {
      loginButton.disabled = false;
    }
  });

  function logout() {
    setAccessToken("");
    accessSession.hidden = true;
    showLogin();
    onLogout();
    showMessage("Sesión cerrada.");
  }

  document.querySelector("#logout-button").addEventListener("click", logout);
  document.querySelector("#admin-logout-button").addEventListener("click", logout);
}
