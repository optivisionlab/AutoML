"use client";

import { Provider } from "react-redux";
import { store } from "./store";
import { ReactNode } from "react";

interface IProps {
  children: ReactNode;
}

function Providers({ children}: IProps) {
  return (
    <Provider store={store}>{children}</Provider>
  );
}

export default Providers;
