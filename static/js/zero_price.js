$(document).ready(function () {
  if ($.fn.DataTable.isDataTable("#zero_price_products_table")) {
    $("#zero_price_products_table").DataTable().clear().destroy();
  }

  $("#zero_price_products_table").DataTable({
    serverSide: true,
    processing: true,
    responsive: true,
    searching: true,
    pageLength: 50,
    lengthMenu: [50, 100, 500],
    stateSave: false,
    deferRender: true,
    lengthChange: true,
    ordering: false,
    ajax: {
      url: "/zero_price_products_data",
      type: "POST",
      data: function (d) {
        d.page = Math.floor(d.start / d.length) + 1;
        d.per_page = d.length;
        d.draw = d.draw;
        d.search_value = d.search.value;
      },
      dataSrc: function (json) {
        return json.data || [];
      },
    },
    columns: [
      { data: "product_name" },
      { data: "product_description" },
      { data: "product_price" },
      { data: "channel_name" },
      { data: "source_type" },
      { data: "date" },
      {
        data: "media_url",
        render: function (url) {
          return url
            ? `<img src="${url.replace(/\\/g, "/")}" width="40" height="30">`
            : `<span class="text-muted">No Image</span>`;
        },
      },
    ],
    columnDefs: [
      { targets: 4, className: "nowrap-column" },
      { targets: 5, className: "nowrap-column" },
    ],
    language: {
      infoFiltered: "",
      info: "Showing _START_ to _END_ of _TOTAL_ entries",
      processing: "Loading data...",
    },
  });
});
