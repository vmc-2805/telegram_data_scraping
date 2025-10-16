$(document).ready(function () {
  if ($.fn.DataTable.isDataTable("#same_products_table")) {
    $("#same_products_table").DataTable().clear().destroy();
  }
  const $table = $("#same_products_table");
  const $cardBody = $(".card-body");

  $table.addClass("table-loader");

  const shimmerStyle = `
    <style>
    .table-loader {
      visibility: hidden;
      position: relative;
    }
    .table-loader::before {
      visibility: visible;
      display: table-caption;
      content: " ";
      width: 100%;
      height: 500px;
      background-image:
        linear-gradient(rgba(235, 235, 235, 1) 1px, transparent 0),
        linear-gradient(90deg, rgba(235, 235, 235, 1) 1px, transparent 0),
        linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.5) 15%, rgba(255, 255, 255, 0) 30%),
        linear-gradient(rgba(240, 240, 242, 1) 35px, transparent 0);
      background-repeat: repeat;
      background-size:
        1px 35px,
        calc(100% * 0.1666666666) 1px,
        30% 100%,
        2px 70px;
      background-position:
        0 0,
        0 0,
        0 0,
        0 0;
      animation: shine 1.2s infinite linear;
      border-radius: 6px;
    }
    @keyframes shine {
      to {
        background-position:
          0 0,
          0 0,
          40% 0,
          0 0;
      }
    }
    </style>
  `;
  $("head").append(shimmerStyle);

  if ($.fn.DataTable.isDataTable($table)) {
    $table.DataTable().clear().destroy();
  }

  $table.DataTable({
    serverSide: true,
    processing: false,
    responsive: true,
    searching: true,
    pageLength: 50,
    lengthMenu: [50, 100, 500],
    ordering: true,
    lengthChange: true,
    order: [[6, "desc"]],
    ajax: {
      url: "/same_products_data",
      type: "POST",
      data: function (d) {
        d.page = Math.floor(d.start / d.length) + 1;
        d.per_page = d.length;
        d.search_value = d.search.value;
        if (d.order && d.order.length > 0) {
          d.order_column = d.order[0].column;
          d.order_dir = d.order[0].dir;
        } else {
          d.order_column = 6;
          d.order_dir = "desc";
        }
      },
      beforeSend: function () {
        $table.addClass("table-loader");
        $table.find("tbody").hide();
      },
      complete: function () {
        $table.removeClass("table-loader");
        $table.find("tbody").fadeIn(300);
      },
      dataSrc: function (json) {
        return json.data;
      },
    },
    columns: [
      {
        data: "media_url",
        render: function (url) {
          if (!url) return `<span class="text-muted">No Image</span>`;
          const safeUrl = url.replace(/\\/g, "/");
          return `
      <img src="${safeUrl}" 
           width="80" height="80" 
           class="img-thumbnail img-preview" 
           data-img="${safeUrl}" 
           style="cursor:pointer;">
    `;
        },
      },
      { data: "product_name" },
      { data: "product_price" },
      { data: "channel_name" },
      {
        data: "product_description",
        render: function (text) {
          if (text && text.length > 20) {
            return `<span title="${text}">${text.substring(0, 20)}...</span>`;
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
