$(document).ready(function () {
  loadDashboardCounts();
});

function loadDashboardCounts() {
  $.ajax({
    url: "/dashboard_counts",
    method: "GET",
    dataType: "json",
    cache: false,
    beforeSend: function () {
      $("#total_products, #same_products, #total_channels, #low_price_products").text("0");
    },
    success: function (data) {
      animateCounter("#total_products", data.total_products);
      animateCounter("#same_products", data.same_products);
      animateCounter("#total_channels", data.total_channels);
      animateCounter("#low_price_products", data.low_price_products);
    },
    error: function (xhr, status, error) {
      console.error("Error loading dashboard counts:", error);
    },
  });
}

function animateCounter(selector, targetNumber) {
  const element = $(selector);
  let currentNumber = 0;
  const duration = 1000; 
  const stepTime = 50;   
  const increment = targetNumber / (duration / stepTime);

  const timer = setInterval(() => {
    currentNumber += increment;
    if (currentNumber >= targetNumber) {
      currentNumber = targetNumber;
      clearInterval(timer);
    }
    element.text(Math.round(currentNumber));
  }, stepTime);
}
