document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("loginForm");
  const alertContainer = document.querySelector(".alert-container");

  const togglePassword = document.querySelector(".toggle-password");
  if (togglePassword) {
    togglePassword.addEventListener("click", () => {
      togglePassword.classList.toggle("fa-eye");
      togglePassword.classList.toggle("fa-eye-slash");
      const input = document.querySelector(
        togglePassword.getAttribute("toggle")
      );
      if (input) input.type = input.type === "password" ? "text" : "password";
    });
  }

  const showAlert = (message, type = "danger") => {
    if (!alertContainer) return;
    alertContainer.innerHTML = `
    <div class="alert alert-${type} alert-dismissible fade show mt-2" role="alert">
      ${message}
      <button type="button" class="close" data-dismiss="alert" aria-label="Close">
        <span aria-hidden="true">&times;</span>
      </button>
    </div>
  `;
  };

  const setButtonLoading = (button, loading = true) => {
    if (loading) {
      button.disabled = true;
      button.innerHTML = `
        <span class="shimmer-loader"></span>
        Logging in...
      `;
    } else {
      button.disabled = false;
      button.innerHTML = "Login";
    }
  };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    alertContainer.innerHTML = "";

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value.trim();
    const button = form.querySelector("button");
    setButtonLoading(button, true);

    try {
      const response = await fetch("/login", {
        method: "POST",
        body: new URLSearchParams({ username: email, password }),
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      const data = await response.json().catch(() => ({}));

      if (response.ok && data.success) {
        showAlert("Login successful! Redirecting...", "success");
        document.cookie = `access_token=${data.access_token}; path=/`;
        setTimeout(() => (window.location.href = "/"), 1000);
      } else {
        const msg =
          data.detail ||
          data.message ||
          "Invalid credentials or user not found.";
        showAlert(`${msg}`, "danger");
      }
    } catch (err) {
      console.error(err);
      showAlert("⚠️ Server connection error. Please try again.", "danger");
    } finally {
      setButtonLoading(button, false);
    }
  });
});
