// Entry point: mount the demo component (the .jsx in localdoc stays the single source of truth).
import { createRoot } from "react-dom/client";
import NovaCRMDemo from "../localdoc/novacrm-demo.jsx";

createRoot(document.getElementById("root")).render(<NovaCRMDemo />);
