import { ArrowLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "./ui";

interface BackButtonProps {
  fallbackTo: string;
  label?: string;
  className?: string;
}

export function BackButton({ fallbackTo, label = "返回上一页", className }: BackButtonProps) {
  const navigate = useNavigate();

  const goBack = () => {
    const historyIndex = window.history.state?.idx;
    if (typeof historyIndex === "number" && historyIndex > 0) {
      navigate(-1);
      return;
    }
    navigate(fallbackTo, { replace: true });
  };

  return (
    <Button type="button" variant="ghost" className={className} onClick={goBack}>
      <ArrowLeft className="h-4 w-4" />
      {label}
    </Button>
  );
}
