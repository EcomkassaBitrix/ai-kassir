import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import Icon from '@/components/ui/icon';
import { apiMethods, commonReferences } from '@/data/apiDocs';

const methodColor: Record<string, string> = {
  GET: 'bg-blue-100 text-blue-700 border-blue-200',
  POST: 'bg-green-100 text-green-700 border-green-200',
  OPTIONS: 'bg-gray-100 text-gray-500 border-gray-200',
};

const CodeBlock = ({ code }: { code: string }) => (
  <pre className="bg-slate-950 text-slate-100 rounded-lg p-4 text-xs overflow-x-auto whitespace-pre-wrap break-words">
    <code>{code}</code>
  </pre>
);

const FieldsTable = ({
  title,
  fields,
}: {
  title: string;
  fields: { name: string; type: string; required: boolean; description: string }[];
}) => (
  <div>
    <h4 className="text-sm font-semibold text-muted-foreground mb-2">{title}</h4>
    <div className="rounded-lg border overflow-hidden">
      <table className="w-full text-sm">
        <tbody>
          {fields.map((f) => (
            <tr key={f.name} className="border-b last:border-0">
              <td className="px-3 py-2 font-mono text-xs whitespace-nowrap align-top text-foreground">{f.name}</td>
              <td className="px-3 py-2 text-xs text-muted-foreground whitespace-nowrap align-top">{f.type}</td>
              <td className="px-3 py-2 align-top">
                {f.required ? (
                  <Badge variant="destructive" className="text-[10px]">обязательное</Badge>
                ) : (
                  <Badge variant="outline" className="text-[10px]">опционально</Badge>
                )}
              </td>
              <td className="px-3 py-2 text-xs align-top text-foreground">{f.description}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);

const ApiDocs = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-purple-950/20 p-4">
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-4 mb-2">
          <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
            <Icon name="ArrowLeft" size={20} />
          </Button>
          <div>
            <h1 className="text-2xl font-bold text-foreground">API документация</h1>
            <p className="text-sm text-muted-foreground">
              Описание всех backend-методов проекта: что принимают и что возвращают
            </p>
          </div>
        </div>

        {/* Навигация по методам */}
        <div className="flex flex-wrap gap-2 my-6">
          {apiMethods.map((m) => (
            <a
              key={m.id}
              href={`#${m.id}`}
              className="text-xs font-mono px-2.5 py-1 rounded-md bg-card border text-muted-foreground hover:border-primary hover:text-primary transition-colors"
            >
              {m.name}
            </a>
          ))}
        </div>

        <div className="space-y-6">
          {apiMethods.map((method) => (
            <Card key={method.id} id={method.id} className="p-6 scroll-mt-4">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <h2 className="text-lg font-bold font-mono text-foreground">{method.name}</h2>
                {method.httpMethods.map((hm) => (
                  <span
                    key={hm}
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${methodColor[hm] || ''}`}
                  >
                    {hm}
                  </span>
                ))}
                {method.auth && (
                  <Badge variant="secondary" className="text-[10px] gap-1">
                    <Icon name="Lock" size={10} />
                    {method.auth}
                  </Badge>
                )}
              </div>

              <p className="text-sm text-muted-foreground mb-4">{method.description}</p>

              <div className="space-y-4">
                {method.headers && method.headers.length > 0 && (
                  <FieldsTable title="Заголовки" fields={method.headers} />
                )}

                {method.queryParams && method.queryParams.length > 0 && (
                  <FieldsTable title="Query-параметры" fields={method.queryParams} />
                )}

                {method.requestFields && method.requestFields.length > 0 && (
                  <FieldsTable title="Поля тела запроса" fields={method.requestFields} />
                )}

                {method.requestExample && (
                  <div>
                    <h4 className="text-sm font-semibold text-muted-foreground mb-2">Пример запроса</h4>
                    <CodeBlock code={method.requestExample} />
                  </div>
                )}

                <div>
                  <h4 className="text-sm font-semibold text-muted-foreground mb-2">Пример ответа</h4>
                  <CodeBlock code={method.responseExample} />
                </div>

                <div>
                  <h4 className="text-sm font-semibold text-muted-foreground mb-2">Коды ответа</h4>
                  <div className="flex flex-wrap gap-2">
                    {method.errors.map((e, idx) => (
                      <div
                        key={idx}
                        className="flex items-start gap-2 text-xs bg-muted/50 rounded-md px-2.5 py-1.5"
                      >
                        <span
                          className={`font-mono font-bold ${
                            e.code >= 500
                              ? 'text-red-600'
                              : e.code >= 400
                              ? 'text-orange-600'
                              : 'text-green-600'
                          }`}
                        >
                          {e.code}
                        </span>
                        <span className="text-muted-foreground">{e.description}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {method.notes && (
                  <div className="flex items-start gap-2 text-xs bg-primary/10 text-primary rounded-md p-3">
                    <Icon name="Info" size={14} className="mt-0.5 shrink-0" />
                    <span>{method.notes}</span>
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>

        {/* Справочники значений */}
        <Card className="p-6 mt-6">
          <h2 className="text-lg font-bold mb-4 text-foreground">Общие справочники значений</h2>
          <div className="grid sm:grid-cols-2 gap-4">
            {commonReferences.map((ref) => (
              <div key={ref.title}>
                <h4 className="text-sm font-semibold text-muted-foreground mb-2">{ref.title}</h4>
                <ul className="text-xs space-y-1">
                  {ref.items.map((item) => (
                    <li key={item} className="font-mono bg-muted/50 rounded px-2 py-1 text-foreground">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Card>

        <p className="text-center text-xs text-muted-foreground my-8">
          Актуальные URL методов — в backend/func2url.json
        </p>
      </div>
    </div>
  );
};

export default ApiDocs;