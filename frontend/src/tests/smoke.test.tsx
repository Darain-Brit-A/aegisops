import { render, screen } from "@testing-library/react";
import App from "../App";

describe("AegisOps frontend scaffold", () => {
  it("renders the product title and tagline", () => {
    render(<App />);
    expect(screen.getByText("AegisOps")).toBeInTheDocument();
    expect(screen.getByText("Observe everything. Expose nothing.")).toBeInTheDocument();
  });
});
