// Entry point: mount the demo component (the .jsx in localdoc stays the single source of truth).
import { createRoot } from "react-dom/client";
import EggCRMDemo from "../localdoc/novacrm-demo.jsx";

createRoot(document.getElementById("root")).render(<EggCRMDemo />);
