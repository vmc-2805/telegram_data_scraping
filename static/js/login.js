document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("loginForm");

    form.addEventListener("submit", async (e) => {
        e.preventDefault(); 

        const email = document.getElementById("email").value;
        const password = document.getElementById("password").value;

        const formData = new URLSearchParams();
        formData.append("username", email); 
        formData.append("password", password);

        try {
            const response = await fetch("/login", {
                method: "POST",
                body: formData,
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded"
                }
            });

            if (response.ok) {
                const data = await response.json();

                if (data.success) {
                    console.log("Login Success:", data);
                    document.cookie = `access_token=${data.access_token}; path=/`;
                    window.location.href = "/";
                } else {
                    alert("Login failed: " + data.detail);
                }
            } else {
                const errorData = await response.json().catch(() => ({ detail: "Unknown error" }));
                alert("Login failed: " + errorData.detail);
            }
        } catch (err) {
            console.error(err);
            alert("An error occurred. Please try again.");
        }
    });
});
