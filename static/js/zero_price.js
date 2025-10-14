$("body").append(`
  <div id="table-loader"
       style="
         position: fixed;
         top: 285px;
         left: 248px;
         width: calc(100vw - 270px);
         height: calc(100vh - 285px);
         background: rgba(255, 255, 255, 0.8);
         z-index: 9999;
         display: none;
         border-radius: 6px;
       ">
    <div class="h-100 d-flex align-items-center justify-content-center text-center">
      <div class="spinner-border text-primary" style="width:3rem;height:3rem;" role="status"></div>
      <div class="px-2">Loading data...</div>
    </div>
  </div>
`);

$(document).ready(function () {
  if ($.fn.DataTable.isDataTable("#zero_price_products_table")) {
    $("#zero_price_products_table").DataTable().clear().destroy();
  }

  $("#zero_price_products_table").DataTable({
    serverSide: true,
    processing: false,
    responsive: true,
    searching: true,
    pageLength: 50,
    lengthMenu: [50, 100, 500],
    stateSave: false,
    deferRender: true,
    lengthChange: true,
    ordering: true,
    ajax: {
      url: "/zero_price_products_data",
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
          d.order_column = 1;
          d.order_dir = "desc";
        }
      },
      beforeSend: function () {
        $("#table-loader").fadeIn(200);
      },
      complete: function () {
        $("#table-loader").fadeOut(200);
      },
      dataSrc: function (json) {
        return json.data || [];
      },
    },
    columns: [
      {
        data: "media_url",
        render: function (url) {
          return url
            ? `<img src="${url.replace(/\\/g, "/")}" width="50" height="40">`
            : `<span class="text-muted">No Image</span>`;
        },
      },
      { data: "product_name" },
      { data: "product_price" },
      { data: "channel_name" },
      {
        data: "product_description",
        render: function (text, type, row) {
          if (text && text.length > 20) {
            return text.substring(0, 20) + "...";
          }
          return text;
        },
      },
      { data: "source_type" },
      { data: "date" },
    ],
    columnDefs: [{ targets: [1, 4, 5, 6], className: "nowrap-column" }],
    language: {
      infoFiltered: "",
      info: "Showing _START_ to _END_ of _TOTAL_ entries",
      processing: "",
    },
  });
});
