import Image from "next/image";
import Link from "next/link";

interface LogoProps {
  className?: string;
  size?: number;
  showText?: boolean;
  textColor?: string;
}

export function TenderLexLogo({
  className = "",
  size = 34,
  showText = true,
  textColor = "text-teal-700",
}: LogoProps) {
  return (
    <Link href="/" className={`inline-flex items-center gap-2.5 hover:opacity-90 transition-opacity ${className}`}>
      <Image
        src="/tenderlex-logo.png"
        alt="TenderLex Logo"
        width={size}
        height={size}
        className="rounded-lg object-contain shrink-0"
        priority
      />
      {showText && (
        <span className={`font-black text-xl tracking-tight ${textColor}`}>
          TenderLex
        </span>
      )}
    </Link>
  );
}