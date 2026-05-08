//===----------------------------------------------------------------------===//
//
// Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
//===----------------------------------------------------------------------===//

// UNSUPPORTED: c++03
// ADDITIONAL_COMPILE_FLAGS: -fsanitize=undefined -fsanitize-trap=undefined

#include <cstddef>
#include <cstring>
#include <new>
#include <vector>

class Optional {
public:
  Optional()                           = default;
  Optional(const Optional&)            = default;
  Optional& operator=(const Optional&) = default;
  Optional(Optional&&) {}

  template <class Arg>
  Optional& operator=(Arg&&) {
    if (hasValue()) {
      hasValue_ = false;
    }
    return *this;
  }

  bool hasValue() const { return hasValue_; }

private:
  bool hasValue_ = false;
};

template <class T>
struct PoisoningAllocator {
  using value_type     = T;
  PoisoningAllocator() = default;
  template <class U>
  PoisoningAllocator(const PoisoningAllocator<U>&) noexcept {}
  T* allocate(std::size_t n) {
    void* p = ::operator new(n * sizeof(T));
    std::memset(p, 0xBE, n * sizeof(T));
    return static_cast<T*>(p);
  }
  void deallocate(T* p, std::size_t) noexcept { ::operator delete(p); }
};

template <class T, class U>
bool operator==(const PoisoningAllocator<T>&, const PoisoningAllocator<U>&) noexcept {
  return true;
}
template <class T, class U>
bool operator!=(const PoisoningAllocator<T>&, const PoisoningAllocator<U>&) noexcept {
  return false;
}

int main(int, char**) {
  std::vector<Optional, PoisoningAllocator<Optional>> src(1);
  auto dst = src;
  (void)dst[0].hasValue();
  return 0;
}
