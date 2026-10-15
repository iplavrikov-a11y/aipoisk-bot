import Image from "next/image";
import Link from "next/link";

interface LogoProps {
  className?: string;
  size?: number;
  showText?: boolean;
  textColor?: string;
  link?: boolean;
}

export function TenderLexLogo({
  className = "",
  size = 34,
  showText = true,
  textColor = "text-teal-700",
  link = true,
}: LogoProps) {
  const content = (
    <div className={`inline-flex items-center gap-2.5 shrink-0 ${className}`}>
      <Image
        src="/tenderlex-logo.png"
        alt="TenderLex"
        width={size}
        height={size}
        className="rounded-lg object-contain shrink-0"
        priority
      />
      {showText && (
        <span className={`font-black text-xl tracking-tight shrink-0 ${textColor}`}>
          TenderLex
        </span>
      )}
    </div>
  );

  if (link) {
    return (
      <Link href="/" className="inline-flex shrink-0 hover:opacity-90 transition-opacity">
        {content}
      </Link>
    );
  }

  return content;
}