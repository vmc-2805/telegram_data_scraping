document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("loginForm");
  const alertContainer = document.querySelector(".alert-container");

  // Password toggle
  const togglePassword = document.querySelector(".toggle-password");
  if (togglePassword) {
    togglePassword.addEventListener("click", () => {
      togglePassword.classList.toggle("fa-eye");
      togglePassword.classList.toggle("fa-eye-slash");
      const input = document.querySelector(togglePassword.getAttribute("toggle"));
      if (input) input.type = input.type === "password" ? "text" : "password";
    });
  }

  // Function to show alerts
  const showAlert = (message, type = "danger") => {
    if (!alertContainer) return;
    alertContainer.innerHTML = `
      <div class="alert alert-${type} alert-dismissible fade show" role="alert">
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
      </div>
    `;
  };

  // Function to animate button with shimmer loader
  const setButtonLoading = (button, loading = true) => {
    if (loading) {
      button.disabled = true;
      button.innerHTML = `
        <span class="shimmer-loader"></span>
        Logging in...
      `;
      button.style.position = "relative";
      button.style.overflow = "hidden";
    } else {
      button.disabled = false;
      button.innerHTML = "Login";
    }
  };

  // Form submit handler
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showAlert(""); // clear any previous alerts

    const email = document.getElementById("email").value;
    const password = document.getElementById("password").value;

    const button = form.querySelector("button");
    setButtonLoading(button, true);

    try {
      const response = await fetch("/login", {
        method: "POST",
        body: new URLSearchParams({ username: email, password }),
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
      });

      const data = await response.json();

      if (response.ok && data.success) {
        showAlert("Login successful! Redirecting...", "success");
        document.cookie = `access_token=${data.access_token}; path=/`;
        setTimeout(() => window.location.href = "/", 1000);
      } else {
        showAlert(`Login failed: ${data.detail || "Unknown error"}`, "danger");
      }
    } catch (err) {
      console.error(err);
      showAlert("An error occurred. Please try again.", "danger");
    } finally {
      setButtonLoading(button, false);
    }
  });
});
