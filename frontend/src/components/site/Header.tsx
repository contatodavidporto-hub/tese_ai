import Link from "next/link";

// Cabeçalho do site: marca serifada + navegação mínima. O traço duplo inferior
// (linha forte + hairline) é a assinatura visual de "papel timbrado".
export function Header() {
  return (
    <header className="border-b border-linha bg-papel">
      <div className="mx-auto flex w-full max-w-5xl items-baseline justify-between gap-4 px-4 py-4 sm:px-6">
        <Link
          href="/"
          className="font-display text-xl font-semibold tracking-tight text-tinta"
        >
          Tese <span className="text-selo-texto">AI</span>
        </Link>
        <nav aria-label="Principal" className="flex items-baseline gap-5 text-sm">
          <Link
            href="/tese"
            className="text-tinta-2 underline-offset-4 hover:text-tinta hover:underline"
          >
            Gerar tese
          </Link>
          <Link
            href="/historico"
            className="text-tinta-2 underline-offset-4 hover:text-tinta hover:underline"
          >
            Histórico
          </Link>
        </nav>
      </div>
      <div className="h-px bg-linha-forte" aria-hidden />
    </header>
  );
}
