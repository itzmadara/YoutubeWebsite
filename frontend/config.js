window.CLIPFORGE_API_BASE_URL = (
  window.location.hostname === "127.0.0.1" ||
  window.location.hostname === "localhost"
)
  ? "http://127.0.0.1:8000"
  : "https://utubfrontend-2273993efc66.herokuapp.com";
