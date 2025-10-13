$(document).ready(function () {
  // Call immediately when page loads
  loadDashboardCounts();
});

function loadDashboardCounts() {
  $.ajax({
    url: "/dashboard_counts",
    method: "GET",
    dataType: "json",
    cache: false, // no cache, always fresh
    beforeSend: function () {
      // optional: show loading spinner
      $("#total_products, #same_products, #total_channels, #low_price_products")
        .text("...");
    },
    success: function (data) {
      $("#total_products").text(data.total_products);
      $("#same_products").text(data.same_products);
      $("#total_channels").text(data.total_channels);
      $("#low_price_products").text(data.low_price_products);
    },
    error: function (xhr, status, error) {
      console.error("Error loading dashboard counts:", error);
    },
  });
}
