$(document).ready(function () {
  if ($.fn.DataTable.isDataTable("#all_products_table")) {
    $("#all_products_table").DataTable().clear().destroy();
  }

  $("#all_products_table").DataTable({
    serverSide: true,
    processing: true,
    responsive: true,
    searching: true,
    pageLength: 50,
    lengthMenu: [50, 100, 500],
    ordering: true,
    lengthChange: true,
    order: [[6, "desc"]], 
    ajax: {
      url: "/all_product",
      type: "POST",
      data: function (d) {
        d.page = Math.floor(d.start / d.length) + 1;
        d.per_page = d.length;
        d.draw = d.draw;
        d.search_value = d.search.value;

        if (d.order && d.order.length > 0) {
          d.order_column = d.order[0].column; 
          d.order_dir = d.order[0].dir;       
        } else {
          d.order_column = 6; 
          d.order_dir = "desc";
        }
      },
      dataSrc: function (json) {
        return json.data;
      },
    },
    columns: [
      {
        data: "media_url",
        render: function (url) {
          return url
            ? `<img src="${url.replace(/\\/g, "/")}" width="40" height="30">`
            : `<span class="text-muted">No Image</span>`;
        },
      },
      { data: "product_name" },
      { data: "product_description" },
      { data: "product_price" },
      { data: "channel_name" },
      { data: "source_type" },
      { data: "date" }, 
    ],
    columnDefs: [
      { targets: 5, className: "nowrap-column" },
      { targets: 6, className: "nowrap-column" },
    ],
    language: {
      infoFiltered: "",
      info: "Showing _START_ to _END_ of _TOTAL_ entries",
      processing: "Processing...",
    },
  });
});
