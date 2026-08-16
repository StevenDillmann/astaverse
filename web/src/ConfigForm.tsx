/** The configuration form, rendered from the server's JSON Schema.
 *
 * Nothing here knows what a knob is called. The fields, their types, their
 * ranges and their help text all come from `core/config.py` — the same
 * pydantic model tyro turns into CLI flags. Adding a knob to the tool makes
 * it appear here and at the terminal, with no edit to either surface.
 *
 * Each field also shows the flag that sets it, so the form doubles as
 * documentation for the CLI you would use instead.
 */

import { useEffect, useMemo, useState } from "react";
import { getConfig, getConfigSchema, putConfig } from "./api";
import type { JsonSchema } from "./api";
import { Button, Checkbox, Eyebrow, Field, Input, Select, cn } from "./ui";

type Values = Record<string, any>;

/** Resolve `$ref` so nested sections can be walked like any other schema. */
function resolve(schema: JsonSchema, node: any): any {
  if (node?.$ref) {
    const name = String(node.$ref).split("/").pop()!;
    return schema.$defs?.[name] ?? {};
  }
  return node ?? {};
}

/** A pydantic `str | None` becomes anyOf[string, null]; unwrap to the string. */
function unwrapNullable(node: any): any {
  if (!node?.anyOf) return node;
  const real = node.anyOf.find((o: any) => o.type && o.type !== "null");
  return { ...node, ...(real ?? {}) };
}

function flagFor(section: string | null, field: string): string {
  const name = field.replace(/_/g, "-");
  return section ? `--${section}.${name}` : `--${name}`;
}

function ScalarField({
  section,
  name,
  node,
  value,
  onChange,
}: {
  section: string | null;
  name: string;
  node: any;
  value: any;
  onChange: (v: any) => void;
}) {
  const spec = unwrapNullable(node);
  const label = spec.title || name.replace(/_/g, " ");
  const hint = spec.description;
  const flag = flagFor(section, name);
  const withFlag = (
    <>
      {hint} <code className="font-mono text-[11px] text-muted-foreground/80">{flag}</code>
    </>
  );

  if (spec.enum) {
    return (
      <Field label={label} hint={withFlag as any}>
        <Select value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
          {spec.enum.map((o: string) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </Select>
      </Field>
    );
  }

  if (spec.type === "boolean") {
    return <Checkbox checked={!!value} onChange={onChange} label={label} hint={hint} />;
  }

  if (spec.type === "integer" || spec.type === "number") {
    return (
      <Field label={label} hint={withFlag as any}>
        <Input
          type="number"
          value={value ?? ""}
          min={spec.minimum}
          max={spec.maximum}
          step={spec.type === "integer" ? 1 : "any"}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        />
      </Field>
    );
  }

  if (spec.type === "array") {
    return (
      <Field label={label} hint={withFlag as any}>
        <Input
          placeholder="comma-separated"
          value={Array.isArray(value) ? value.join(", ") : ""}
          onChange={(e) =>
            onChange(
              e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            )
          }
        />
      </Field>
    );
  }

  return (
    <Field label={label} hint={withFlag as any}>
      <Input
        placeholder="default"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      />
    </Field>
  );
}

export function ConfigForm({
  analysisId,
  onSaved,
}: {
  analysisId: string;
  onSaved?: (values: Values) => void;
}) {
  const [schema, setSchema] = useState<JsonSchema | null>(null);
  const [values, setValues] = useState<Values | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getConfigSchema().then(setSchema).catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    setSaved(false);
    getConfig(analysisId).then(setValues).catch((e) => setError(e.message));
  }, [analysisId]);

  // Sections are object-valued properties; scalars at the root (like
  // `through`) are grouped separately so the layout follows the schema.
  const { sections, scalars } = useMemo(() => {
    const sections: [string, any][] = [];
    const scalars: [string, any][] = [];
    for (const [name, node] of Object.entries(schema?.properties ?? {})) {
      const resolved = resolve(schema!, node);
      if (resolved.type === "object" || resolved.properties) sections.push([name, resolved]);
      else scalars.push([name, node]);
    }
    return { sections, scalars };
  }, [schema]);

  if (error) return <p className="text-xs text-single">{error}</p>;
  if (!schema || !values) return <p className="text-[13px] text-muted-foreground">Loading…</p>;

  const set = (section: string | null, field: string, v: any) => {
    setValues((current) =>
      section
        ? { ...current, [section]: { ...(current as Values)[section], [field]: v } }
        : { ...current, [field]: v },
    );
    setSaved(false);
  };

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const next = await putConfig(analysisId, values as Values);
      setValues(next);
      setSaved(true);
      onSaved?.(next);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="mb-6 rounded-md border border-border bg-muted/40 px-3 py-2 text-xs leading-relaxed text-muted-foreground">
        Every field below is generated from the same definition that produces the CLI flags, so
        anything you set here can be typed instead — the flag is shown under each one.
      </div>

      <div className="grid gap-x-10 gap-y-2 md:grid-cols-2 xl:grid-cols-3">
        {sections.map(([section, node]) => (
          <section key={section}>
            <Eyebrow className="mb-3">{section}</Eyebrow>
            {Object.entries(node.properties ?? {}).map(([field, fieldNode]) => (
              <ScalarField
                key={field}
                section={section}
                name={field}
                node={fieldNode}
                value={values[section]?.[field]}
                onChange={(v) => set(section, field, v)}
              />
            ))}
          </section>
        ))}

        {scalars.length > 0 && (
          <section>
            <Eyebrow className="mb-3">run</Eyebrow>
            {scalars.map(([field, node]) => (
              <ScalarField
                key={field}
                section={null}
                name={field}
                node={node}
                value={values[field]}
                onChange={(v) => set(null, field, v)}
              />
            ))}
          </section>
        )}
      </div>

      <div className={cn("mt-6 flex items-center gap-3 border-t border-border pt-5")}>
        <Button variant="primary" onClick={save} disabled={saving}>
          {saving ? "Saving…" : "Save configuration"}
        </Button>
        {saved && <span className="text-xs text-ok">Saved — used by every stage from now on.</span>}
      </div>
    </>
  );
}
