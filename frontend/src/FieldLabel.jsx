import { useState } from "react";
import { CircleHelp } from "lucide-react";

export function FieldLabel({ htmlFor, label, description, children }) {
  const [open, setOpen] = useState(false);
  const helpId = `${htmlFor}-help`;
  return <>
    <div className="field-label-row">
      {children || <label htmlFor={htmlFor}>{label}</label>}
      <button className="field-help-button" type="button" title={description}
        aria-label={`About ${label}`} aria-expanded={open} aria-controls={helpId}
        onClick={() => setOpen(!open)} onKeyDown={(event) => { if (event.key === "Escape") setOpen(false); }}>
        <CircleHelp size={16} aria-hidden="true" />
      </button>
    </div>
    <p className="field-help-text" id={helpId} hidden={!open}>{description}</p>
  </>;
}
