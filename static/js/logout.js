document.addEventListener("DOMContentLoaded", () => {
    const logoutBtn = document.getElementById("logoutBtn");

    if (!logoutBtn) return;

    logoutBtn.addEventListener("click", async () => {
        const match = document.cookie.match(/access_token=([^;]+)/);
        const token = match ? match[1] : null;

        if (!token) {
            alert("No token found. You are already logged out.");
            return;
        }

        try {
            const response = await fetch("/logout", {
                method: "POST",
                headers: {
                    "Authorization": "Bearer " + token
                }
            });

            const data = await response.json();

            if (data.message) {
                alert(data.message);
                // Remove cookie
                document.cookie = "access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                window.location.href = "/login"; 
            } else {
                alert("Logout failed");
            }
        } catch (err) {
            console.error(err);
            alert("An error occurred during logout");
        }
    });
});
